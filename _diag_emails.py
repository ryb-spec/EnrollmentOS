import dashboard, config
pages = dashboard.load_pages()
pros = [p for p in pages if p.get('_source')=='New Prospects']
email_prop = config.PROP_STUDENT_EMAIL
alt_prop = config.PROP_STUDENT_ALT_EMAIL

def has_val(prop):
    if not prop:
        return False
    t = prop.get('type')
    if t == 'email':
        return bool(prop.get('email'))
    if t == 'rich_text':
        return bool(''.join(x.get('plain_text','') for x in (prop.get('rich_text') or [])).strip())
    return False

email_count = 0
alt_count = 0
for page in pros:
    props = page.get('properties', {})
    if has_val(props.get(email_prop)):
        email_count += 1
    if has_val(props.get(alt_prop)):
        alt_count += 1
print('Prospects:', len(pros))
print(f"{email_prop} populated:", email_count)
print(f"{alt_prop} populated:", alt_count)
