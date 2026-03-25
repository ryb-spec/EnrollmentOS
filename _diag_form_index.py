import google_forms, config
idx = google_forms.load_google_form_indexes(config)
for k,v in idx.get('forms',{}).items():
    print(k, 'error=', v.get('error'), 'rows=', len(v.get('rows',[])) if isinstance(v.get('rows'), list) else 'n/a')
