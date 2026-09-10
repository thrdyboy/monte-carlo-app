def _flatten_metadata(metadata: dict) -> list[tuple[str, object]]:
    """Yield (key, value) pairs; need to expand nested dicts into 'parent.child' Keys."""
    rows = []
    for k, v in metadata.items():
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                rows.append((f"{k}.{sub_k}", sub_v))
        else:
            rows.append((k, v))
    return rows