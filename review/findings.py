"""Regrouper les répétitions sans perdre un constat ni ses preuves."""
SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def catalog(results, tools):
    entries = {
        f"agent-{result.agent}-{index}": finding
        for result in results if result.agent != 7
        for index, finding in enumerate(result.findings, 1)
    }
    entries.update({
        f"outil-{name}-{index}": finding
        for name, tool in tools.items()
        for index, finding in enumerate(tool.findings, 1)
    })
    return entries


def consolidate(entries, proposals):
    # Les doublons textuels sont regroupés même si la synthèse IA échoue.
    exact = {}
    for reference, finding in entries.items():
        key = (finding.file, finding.line, finding.title, finding.evidence)
        exact.setdefault(key, []).append(reference)
    groups = list(exact.values())
    rejected = False
    for proposal in proposals:
        refs = list(dict.fromkeys(proposal))
        if len(refs) < 2 or any(ref not in entries for ref in refs):
            rejected = True
            continue
        locations = {(entries[ref].file, entries[ref].line) for ref in refs}
        if len(locations) != 1 or any(file is None or line is None for file, line in locations):
            rejected = True
            continue
        selected = [group for group in groups if any(ref in group for ref in refs)]
        merged = [ref for ref in entries if any(ref in group for group in selected)]
        groups = [group for group in groups if group not in selected] + [merged]
    groups.sort(key=lambda group: min(SEVERITY[entries[ref].severity] for ref in group))
    return groups, rejected


def validate_groups(entries, groups):
    refs = [ref for group in groups for ref in group]
    if any(not group for group in groups) or len(refs) != len(set(refs)) or set(refs) != set(entries):
        raise ValueError("Les groupes doivent conserver chaque constat exactement une fois")
    for group in groups:
        locations = {(entries[ref].file, entries[ref].line) for ref in group}
        if len(locations) > 1:
            raise ValueError("Un regroupement ne peut pas mélanger plusieurs emplacements")
