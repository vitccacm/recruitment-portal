// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyC3LKoXvKYAGuFf61Y1chAC2OxXTy2CuVU",
  authDomain: "acm-recruitment-4886d.firebaseapp.com",
  projectId: "acm-recruitment-4886d",
  storageBucket: "acm-recruitment-4886d.firebasestorage.app",
  messagingSenderId: "518012931766",
  appId: "1:518012931766:web:afe6f92b35eb570c83a017"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

// Export for use in other files
export { auth, provider, signInWithPopup, signOut };
