# Firebase Authentication Setup Guide

This application uses Firebase Authentication with Google Sign-In for student authentication.

## Prerequisites

- Firebase project created at [Firebase Console](https://console.firebase.google.com/)
- Google Cloud project linked to Firebase

## Setup Steps

### 1. Enable Google Sign-In in Firebase

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (`acm-recruitment-4886d`)
3. Navigate to **Authentication** > **Sign-in method**
4. Enable **Google** as a sign-in provider
5. Add your authorized domains (e.g., `localhost`, your production domain)

### 2. Get Firebase Configuration

Your Firebase config is already set in `app/static/js/firebase-config.js`:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyC3LKoXvKYAGuFf61Y1chAC2OxXTy2CuVU",
  authDomain: "acm-recruitment-4886d.firebaseapp.com",
  projectId: "acm-recruitment-4886d",
  storageBucket: "acm-recruitment-4886d.firebasestorage.app",
  messagingSenderId: "518012931766",
  appId: "1:518012931766:web:afe6f92b35eb570c83a017"
};
```

### 3. Generate Firebase Admin SDK Private Key

For backend token verification:

1. Go to **Project Settings** > **Service Accounts**
2. Click **Generate New Private Key**
3. Download the JSON file
4. Extract the following values and add them to your `.env` file:

```env
FIREBASE_PRIVATE_KEY_ID=<value from json: private_key_id>
FIREBASE_PRIVATE_KEY="<value from json: private_key>"
FIREBASE_CLIENT_EMAIL=<value from json: client_email>
FIREBASE_CLIENT_ID=<value from json: client_id>
FIREBASE_CERT_URL=<value from json: client_x509_cert_url>
```

**Important:** The `FIREBASE_PRIVATE_KEY` should be enclosed in double quotes and keep the newlines as `\n`.

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `firebase-admin==6.3.0` along with other dependencies.

### 5. Test Authentication Flow

1. Start the Flask app:
   ```bash
   python run.py
   ```

2. Navigate to `/auth/login`
3. Click "Sign in with Google"
4. The Firebase popup should appear
5. After signing in, you'll be redirected to the student dashboard

## Security Notes

- **Never commit** your Firebase private key to version control
- Keep your `.env` file private
- In production, use environment variables or a secrets manager
- The Firebase config in the frontend is safe to expose (it's meant to be public)
- Backend token verification ensures security even if someone copies the frontend config

## Troubleshooting

### "Invalid authentication token"
- Check that your Firebase Admin SDK credentials are correct in `.env`
- Ensure the private key has proper newline characters (`\n`)

### "Email not provided by Google"
- Ensure Google Sign-In is properly configured in Firebase Console
- Check that email scope is requested

### CORS errors
- Add your domain to Firebase authorized domains
- Check that `authDomain` in firebase-config.js is correct

### Module not found: firebase-admin
- Run `pip install -r requirements.txt`
- Ensure you're using the correct Python environment

## Admin Access

Admin login still uses traditional email/password authentication and is separate from Firebase.
Access admin portal at `/admin/login`.
