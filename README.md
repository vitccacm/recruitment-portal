# ACM Recruitment Portal

A comprehensive recruitment management system for ACM Student Chapters, featuring role-based access control, custom application flows, and a multi-round recruitment process.

## 📚 Documentation
- **[Project Roadmap & TODOs](TODO.md)**: planned features and improvements.

## ✨ Features

### 🔐 Authentication & Security
- **Configurable Auth:** Support for Google OAuth and Email/Password login.
- **Domain Restriction:** Optional restriction to specific email domains (e.g., `@vit.ac.in`).
- **Role-Based Access Control (RBAC):**
  - **Super Admin:** Full system control.
  - **Department Admin:** Manage specific department applications and rounds.
  - **Student:** Apply and track status.
- **Secure Sessions:** Protection against unauthorized access; no-cache headers for logout security.

### 👥 Student Portal
- **Dashboard:** Overview of application status and active recruitments.
- **Profile Management:**
  - Basic details (Name, Reg No, Branch, etc.).
  - **Custom Profile Fields:** Dynamic fields configured by admins.
- **Application System:**
  - Browse available departments.
  - Apply with **Custom Questions** (Text, File Upload, MCQ, etc.).
  - View application history.
- **Rounds Status:** Track progress through recruitment rounds.

### 🛠️ Super Admin Panel
- **Dashboard:** Global statistics and recruitment overview.
- **Department Management:**
  - Create/Edit/Delete departments.
  - Toggle active status.
  - Set recruitment timeline.
- **Account Management:** Manage admin and department admin accounts.
- **Rounds Management:**
  - Define global rounds (e.g., "Aptitude", "Interview").
  - Manage round visibility and locking per department.
- **Customization:**
  - **Global Profile Fields:** Add custom fields to student profiles.
  - **Department Questions:** Manage application questions for any department.
  - **Site Settings:** Configure auth methods and restrictions.
- **Candidate Management:**
  - View all applications.
  - Detailed Applicant View (Profile + Answers).
  - Manage candidates in specific rounds.

### 🏢 Department Admin Panel
- **Dedicated Dashboard:** Stats for specific department.
- **Application Management:**
  - View incoming applications.
  - Review custom question responses.
- **Round Management:**
  - Shortlist candidates for each round.
  - Add internal notes for candidates.
  - Toggle round visibility and results release.
- **Custom Questions:** Configure specific questions for department applications.

## 🚀 Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd recruit
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    - Copy `.env.example` to `.env`
    - Update the variables (Secret Key, Google OAuth credentials, etc.)

5.  **Run the application:**
    ```bash
    python run.py
    ```
    The app will start at `http://localhost:5000`.

## 📂 Project Structure
- `app/admin`: Super admin routes and logic.
- `app/dept`: Department admin routes.
- `app/student`: Student portal routes.
- `app/auth`: Authentication logic.
- `app/main`: Public landing pages.
- `app/models.py`: Database models.
- `app/templates`: Jinja2 templates for UI.
- `app/static`: CSS, images, and file uploads.
