import requests
url = 'https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSyCb6427r_ZXs6ENgjk7newJimpEYRsM4fo'
models = []
res = requests.get(url).json()
models.extend(res.get('models', []))
while res.get('nextPageToken'):
    res = requests.get(url + '&pageToken=' + res['nextPageToken']).json()
    models.extend(res.get('models', []))

valid_models = [m['name'].replace('models/', '') for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
for m in valid_models:
    print(m)
