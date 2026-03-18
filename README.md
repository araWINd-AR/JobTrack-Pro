# JobTrack Pro

JobTrack Pro is a personal job application tracking web app I built after noticing a very common problem during the job search process.

A lot of people around me, especially friends who were actively applying for internships and full-time roles, were struggling to stay organized. Applications were getting tracked in random notes, deadlines were being missed, resumes were hard to manage, and follow-ups were often forgotten. After seeing the same issue again and again, I decided to build a simple solution that could actually help.

That is how JobTrack Pro started.

Instead of creating just another demo project, I wanted to build something practical and useful for real job seekers. I also took feedback from my friends and added features based on the problems they were facing while applying to jobs. The result is a job tracking platform that helps manage applications, resumes, interview notes, follow-ups, and more in one place.

## Features

- User registration and login
- Add, edit, and delete job applications
- Track application status  
  (Saved, Applied, In Progress, Interview, Rejected, Accepted, Offer)
- Due date and follow-up date tracking
- Resume upload and PDF preview
- Resume version tracking
- Interview notes
- Rejection reason tracking
- Job source tracking
- Salary and work mode details
- Job description snapshot storage
- Search and filter options
- CSV export
- Light theme and Dark theme support
- Dashboard insights for applications, interviews, follow-ups, and overdue deadlines

## Why I Built This

This project came from a real problem, not just an idea.

While applying for jobs, I realized that many people were facing the same challenges:
- forgetting which jobs they already applied to
- losing track of follow-up dates
- not remembering which resume version was used
- missing deadlines
- keeping interview notes in separate places

I wanted to create something that makes the job application process more organized and less stressful. This project is my attempt to solve that in a practical way.

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, Jinja Templates
- **File Handling:** Resume upload and preview support for PDF files

## Project Structure

```
job_tracker_app/
│── app.py
│── requirements.txt
│── jobtracker.db
│── uploads/
│── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    └── job_form.html
```


## How to Run Locally

Clone the repository

git clone https://github.com/araWIND-AR/JobTrack-Pro.git
cd JobTrack-Pro

Install dependencies

pip install -r requirements.txt

Run the Flask app

python app.py

Open in browser

http://127.0.0.1:5000
Demo Account

You can use this demo login:

Email: demo@example.com

Password: demo123

Project Demo

I also created a full demo video for this project on YouTube:

YouTube Demo:
https://www.youtube.com/watch?v=veV6JDrqH_k

What Makes This Project Different

What I like most about this project is that it did not begin as just another “project idea.”

It came from a real problem that I personally noticed and that many people around me were facing. I used my friends’ feedback, their struggles, and common job-hunting pain points to shape the features of this application.

So this project is not just a CRUD web app. It is a solution built around a real use case.

Future Improvements

There are still many improvements I would like to make in future versions, such as:

Kanban board view for applications

Better analytics and charts

Reminder notifications

More detailed company tracking

Cover letter version management

Better mobile responsiveness

Calendar view for follow-ups and deadlines

Integration of similar tracking features into my TaskFlow project

Inspiration Behind the Next Step

This project also gave me ideas for improving my broader productivity system. I plan to bring similar tracking and organization features into my TaskFlow project so it can become even more useful for personal workflow management.

Final Thoughts

JobTrack Pro means a lot to me because it was built around a real challenge that many people face during job hunting.

This project helped me think beyond just coding features and focus more on solving an actual user problem. It also showed me how useful it is to listen to people’s struggles, understand their workflow, and build something practical around that.

If you check out the project and have any suggestions, feedback, or ideas for improvement, feel free to share them.

Author

Aravind Ganipisetty
