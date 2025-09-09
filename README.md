# 🗓️ Google Calendar Desktop App

O aplicație **desktop** scrisă în **Python** care îți permite să vezi, să ștergi și să gestionezi evenimentele din Google Calendar într-o interfață simplă și modernă.  



## 🚀 Funcționalități
- Autentificare cu contul Google prin **OAuth2**
- Vizualizare calendar (lună/an, săptămâni, zile)
- Vizualizare evenimentele zilei selectate
- Ștergere eveniment din Google Calendar
- Buton **Refresh** pentru actualizarea evenimentelor
- Buton **Logout** pentru delogare rapidă
- Dark mode personalizat pentru o experiență modernă



## 🛠️ Cerințe
- **Python 3.10+** (testat pe Python 3.13)
- Un cont de **Google** cu Calendar activat



## 📦 Instalare

Clonează repository-ul:

```bash
git clone https://github.com/username/CalendarApp.git
cd CalendarApp
```

Creează și activează un virtual environment (opțional dar recomandat):
```bash
python -m venv venv
.\venv\Scripts\activate   # pe Windows
source venv/bin/activate  # pe Linux / macOS
```

Instalează biblioteci necesare:
```bash
pip install PyQt5 google-api-python-client google-auth-httplib2 google-auth-oauthlib
```



## ⚙️ Configurare Google API

1. Intră pe [Google Cloud Console](https://console.cloud.google.com/)
2. Creează un proiect nou.
3. Activează Google Calendar API.
4. Creează un OAuth 2.0 Client ID (tip "Desktop App").
5. Descarcă fișierul JSON și redenumește-l în credentials.json.
6. Pune fișierul în folderul proiectului (lângă app.py).
7. La prima rulare, aplicația va deschide browserul pentru login și va salva un token.pkl local.

⚠️ **Notă:** Nu se poate posta direct fișierul `credentials.json` pe GitHub, deoarece conține **chei secrete** care permit accesul la contul tău Google. Fiecare utilizator trebuie să își genereze propriul fișier pentru securitate. 
---


## ▶️ Rulare
Deschideți terminalul în locația aplicației și rulați următoarea comandă: 
```bash
python app.py
```



## 📸 Screenshot-uri 
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/c1925de9-69fd-4c1b-94f1-3986b9bbc56c" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/c144c06a-1f46-4de4-9d99-4fe0292fc5ae" />
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/2de25a77-cca2-4613-9225-6615b100697e" />



## 📜 Licență

MIT License – poți folosi și modifica aplicația liber.



## ✨ Autor

Creat de Ghițu Luis Federico, folosind urmatoarele biblioteci:
- PyQt5
- google-api-python-client
- google-auth-httplib2
- google-auth-oauthlib
