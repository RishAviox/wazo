def translate_units_en_to_he(entries: dict):
    translation_metrics = {
                'min': '‘דק',
                'km/h': 'קמ״ש',
                'km': 'ק”מ',
                'm': 'מ׳'
            }
    
    for key, value in entries.items():
        for t_key, t_value in translation_metrics.items():
            if isinstance(value, str) and value.lower().endswith(t_key):
                entries[key] = entries[key].lower().replace(t_key, t_value)
    
    return entries
