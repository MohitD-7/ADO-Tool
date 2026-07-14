from __future__ import annotations

import pandas as pd


ROLE_PARENT = "Parent"
ROLE_CHILD = "Child"
ROLE_STANDALONE = "Standalone"
ROLE_OPTIONS = [ROLE_STANDALONE, ROLE_PARENT, ROLE_CHILD]


def _clean(value) -> str:
    return str(value or "").strip()


def current_relationships(queue_df: pd.DataFrame) -> list[dict]:
    """Read each row's role out of the positional queue encoding.

    In the queue, 'Parent (N)' marks a parent, a blank ATR Type marks a child of
    the most recent parent, and anything else is standalone.
    Returns [{item_no, title, role, parent_sku}] in queue order.
    """
    rows: list[dict] = []
    current_parent = ""
    if queue_df is None or queue_df.empty:
        return rows
    for _, row in queue_df.iterrows():
        item_no = _clean(row.get("Item No", ""))
        if not item_no:
            continue
        atr = _clean(row.get("ATR Type", ""))
        if atr.lower().startswith("parent"):
            role, parent_sku = ROLE_PARENT, ""
            current_parent = item_no
        elif atr == "" and current_parent:
            role, parent_sku = ROLE_CHILD, current_parent
        else:
            role, parent_sku = ROLE_STANDALONE, ""
            current_parent = ""
        rows.append({
            "item_no": item_no,
            "title": _clean(row.get("Title", "")),
            "role": role,
            "parent_sku": parent_sku,
        })
    return rows


def apply_relationships(queue_df: pd.DataFrame, assignments: dict[str, tuple[str, str]]) -> tuple[pd.DataFrame, list[str]]:
    """Rewrite the queue with new roles, regroup children under their parents,
    and relabel ATR Type. Returns (new_queue_df, warnings).

    assignments maps item_no -> (role, parent_sku) and is treated as the full
    desired state; SKUs missing from it keep their current relationship.
    """
    warnings: list[str] = []
    if queue_df is None or queue_df.empty:
        return queue_df, warnings

    records = current_relationships(queue_df)
    known = {entry["item_no"] for entry in records}
    # SKUs whose role/parent the user actually changed this apply (the editor
    # submits every row, so "explicit" means "differs from the current state").
    changed = {
        entry["item_no"]
        for entry in records
        if entry["item_no"] in assignments
        and tuple(assignments[entry["item_no"]]) != (entry["role"], entry["parent_sku"])
    }

    # Resolve the requested role for every SKU.
    roles: dict[str, str] = {}
    parents_of: dict[str, str] = {}
    for entry in records:
        sku = entry["item_no"]
        role, parent_sku = assignments.get(sku, (entry["role"], entry["parent_sku"]))
        role = role if role in ROLE_OPTIONS else ROLE_STANDALONE
        parent_sku = _clean(parent_sku)
        if role == ROLE_CHILD:
            if not parent_sku:
                warnings.append(f"{sku}: marked Child without a parent SKU — kept as Standalone.")
                role, parent_sku = ROLE_STANDALONE, ""
            elif parent_sku == sku:
                warnings.append(f"{sku}: cannot be its own parent — kept as Standalone.")
                role, parent_sku = ROLE_STANDALONE, ""
            elif parent_sku not in known:
                warnings.append(f"{sku}: parent {parent_sku} is not in this batch — kept as Standalone.")
                role, parent_sku = ROLE_STANDALONE, ""
        roles[sku] = role
        parents_of[sku] = parent_sku if role == ROLE_CHILD else ""

    # Promote referenced standalones to Parent — unless the user explicitly made
    # them non-parent this apply, in which case their children are orphaned.
    for sku in list(roles):
        parent_sku = parents_of.get(sku, "")
        if not parent_sku:
            continue
        if roles.get(parent_sku) == ROLE_STANDALONE:
            if parent_sku in changed:
                warnings.append(f"{sku}: its parent {parent_sku} was changed to Standalone — {sku} is now Standalone too.")
                roles[sku] = ROLE_STANDALONE
                parents_of[sku] = ""
            else:
                roles[parent_sku] = ROLE_PARENT
                warnings.append(f"{parent_sku}: promoted to Parent because {sku} was assigned under it.")
        elif roles.get(parent_sku) == ROLE_CHILD:
            warnings.append(f"{sku}: parent {parent_sku} is itself a child — {sku} kept as Standalone.")
            roles[sku] = ROLE_STANDALONE
            parents_of[sku] = ""

    children_by_parent: dict[str, list[str]] = {}
    for entry in records:
        sku = entry["item_no"]
        if roles[sku] == ROLE_CHILD:
            children_by_parent.setdefault(parents_of[sku], []).append(sku)

    # Rebuild order: walk the queue, emit parents followed by their children and
    # standalones as they come; children are emitted only under their parent.
    order: list[str] = []
    for entry in records:
        sku = entry["item_no"]
        if roles[sku] == ROLE_CHILD:
            continue
        order.append(sku)
        if roles[sku] == ROLE_PARENT:
            order.extend(children_by_parent.get(sku, []))

    indexed = queue_df.copy()
    indexed["__sku"] = indexed["Item No"].astype(str).str.strip()
    indexed = indexed.set_index("__sku")
    out = indexed.loc[order].reset_index(drop=True)

    def label(item_no: str) -> str:
        role = roles[item_no]
        if role == ROLE_PARENT:
            return f"Parent ({len(children_by_parent.get(item_no, []))})"
        if role == ROLE_CHILD:
            return ""
        return ROLE_STANDALONE

    out["ATR Type"] = [label(sku) for sku in order]
    return out, warnings
