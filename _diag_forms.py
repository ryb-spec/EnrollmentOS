import dashboard, google_forms, config
pages = dashboard.load_pages()
forms = google_forms.load_google_form_indexes(config)
df = dashboard.pages_to_df(pages, forms)
pros = df[df['Source']=='New Prospects'].copy()
for col in ['Parent Form Submitted','Reference 1 Submitted','Reference 2 Submitted']:
    print('\n'+col)
    print(pros[col].value_counts(dropna=False).to_string())
print('\nSample names with any submission:')
mask = pros[['Parent Form Submitted','Reference 1 Submitted','Reference 2 Submitted']].any(axis=1)
print(pros.loc[mask, ['Name','Status','Parent Form Submitted','Reference 1 Submitted','Reference 2 Submitted']].head(15).to_string(index=False))
