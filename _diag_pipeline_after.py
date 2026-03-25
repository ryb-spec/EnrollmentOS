import dashboard, google_forms, config
pages = dashboard.load_pages()
forms = google_forms.load_google_form_indexes(config)
df = dashboard.pages_to_df(pages, forms)
pros = df[df['Source']=='New Prospects'].copy()
print(pros['Pipeline Stage'].value_counts(dropna=False).to_string())
