# Placement Portal Web Application

This is a complete, full-stack Placement Portal built with Flask, SQLite, and Bootstrap 5.

## Prerequisites
- Python 3.8+
- pip (Python package installer)

## Step-by-Step Setup Instructions

1. **Navigate to the project directory**
   Open your terminal/command prompt and navigate to this folder:
   ```bash
   cd placement_portal
   ```

2. **Create a Virtual Environment (Optional but recommended)**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**
   The application is configured to automatically initialize the database `placement.db` and seed it with a default Admin, a sample Company, and a sample Student when you run it for the first time.
   
   ```bash
   python app.py
   ```

5. **Access the Application**
   Open your web browser and go to:
   [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Default Test Credentials

**Admin User:**
- Email: `admin@placement.com`
- Password: `admin123`

**Sample Company User (Already Approved):**
- Email: `company@test.com`
- Password: `company123`

**Sample Student User:**
- Email: `student@test.com`
- Password: `student123`

## Features Included
- **Role-based Authentication** via Flask-Login (Admin, Company, Student)
- **SQLite Database** created programmatically using Flask-SQLAlchemy
- **Responsive UI** using Bootstrap 5 without any custom JS logic
- **File Uploads** for Student PDF resumes
- **REST API** endpoint for statistics at `/api/stats`
- **Application Workflow**: Company creates drive -> Admin approves -> Student applies -> Company updates status.
