// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDyuJVJaeYZ9E3Lah_V0NKVDB8eARZvkKA",
  authDomain: "acm-recuitement.firebaseapp.com",
  projectId: "acm-recuitement",
  storageBucket: "acm-recuitement.firebasestorage.app",
  messagingSenderId: "453332055457",
  appId: "1:453332055457:web:cc35dc29e5537ee8c707e0"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

// Export for use in other files
export { auth, provider, signInWithPopup, signOut };
