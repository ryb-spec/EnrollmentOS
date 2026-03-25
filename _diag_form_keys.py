import google_forms, config
idx = google_forms.load_google_form_indexes(config)
for fk,form in idx['forms'].items():
    print('\nFORM', fk, 'exists=', form.get('exists'), 'source=', form.get('source'), 'error=', form.get('error'))
    by_name = form.get('by_name', {})
    by_email = form.get('by_email', {})
    print('by_name=', len(by_name), 'by_email=', len(by_email))
    print('sample names:', list(by_name.keys())[:5])
