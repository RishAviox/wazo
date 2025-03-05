def translate_units_en_to_he(entries: dict):
    translations = {
                'Play Time': '‘דק',
                'Kick Power': 'קמ״ש',
                'Dribbling': 'מ׳'
            }
            
    for key, translation in translations.items():
        if key in entries:
            entries[key] = entries[key].replace(entries.get(key).split()[1], translation)
    
    return entries
