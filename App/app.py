from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///university_network.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    major = db.Column(db.String(100))
    year = db.Column(db.String(20))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='normal')  # normal, urgent, event
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
class Club(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100))
    organizer_id = db.Column(db.Integer, db.ForeignKey('club.id'))

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    announcements = Announcement.query.order_by(Announcement.date.desc()).limit(5).all()
    news = News.query.order_by(News.date.desc()).limit(5).all()
    return render_template('dashboard.html', announcements=announcements, news=news)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        
        user = User.query.filter_by(student_id=student_id).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        else:
            flash('Invalid student ID or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get all users who have exchanged messages with the current user
    contacts_query = db.session.query(User).join(
        Message, 
        ((Message.sender_id == User.id) & (Message.receiver_id == user_id)) | 
        ((Message.receiver_id == User.id) & (Message.sender_id == user_id))
    ).distinct()
    
    contacts = []
    for contact in contacts_query:
        # Get the last message exchanged with this contact
        last_message = Message.query.filter(
            ((Message.sender_id == user_id) & (Message.receiver_id == contact.id)) |
            ((Message.receiver_id == user_id) & (Message.sender_id == contact.id))
        ).order_by(Message.timestamp.desc()).first()
        
        # Count unread messages from this contact
        unread_count = Message.query.filter_by(
            sender_id=contact.id, 
            receiver_id=user_id,
            is_read=False
        ).count()
        
        contacts.append({
            'user': contact,
            'last_message': last_message,
            'unread_count': unread_count
        })
    
    return render_template('messages.html', contacts=contacts)

@app.route('/messages/<int:contact_id>', methods=['GET', 'POST'])
def chat(contact_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        content = request.form.get('message')
        if content:
            message = Message(
                sender_id=user_id,
                receiver_id=contact_id,
                content=content
            )
            db.session.add(message)
            db.session.commit()
    
    # Mark messages as read
    unread_messages = Message.query.filter_by(
        sender_id=contact_id,
        receiver_id=user_id,
        is_read=False
    ).all()
    
    for message in unread_messages:
        message.is_read = True
    
    db.session.commit()
    
    # Get all messages between the current user and the contact
    messages = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == contact_id)) |
        ((Message.receiver_id == user_id) & (Message.sender_id == contact_id))
    ).order_by(Message.timestamp).all()
    
    contact = User.query.get_or_404(contact_id)
    
    return render_template('chat.html', messages=messages, contact=contact)

@app.route('/events')
def events():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get current date to separate upcoming and past events
    current_date = datetime.utcnow()
    
    # Query upcoming events (date >= current date)
    upcoming_events = Event.query.filter(Event.date >= current_date).order_by(Event.date).all()
    
    # Query past events (date < current date)
    past_events = Event.query.filter(Event.date < current_date).order_by(Event.date.desc()).all()
    
    return render_template('events.html', upcoming_events=upcoming_events, past_events=past_events)

@app.route('/clubs')
def clubs():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    clubs = Club.query.all()
    print(f"Number of clubs retrieved: {len(clubs)}")
    for club in clubs:
        print(f"Club: {club.name}")
    
    return render_template('clubs.html', clubs=clubs)

@app.route('/events/<int:event_id>')
def event_details(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    event = Event.query.get_or_404(event_id)
    return render_template('event_details.html', event=event)

if __name__ == '__main__':
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created!")
        
        # Check if we need to create test data
        user_count = User.query.count()
        print(f"Current user count: {user_count}")
        
        if not User.query.count():
            print("No users found, creating test data...")
            # Check if we need to create a test user
            if not User.query.filter_by(student_id='test@university.edu').first():
                test_user = User(
                    student_id='test@university.edu',
                    name='Test User',
                    major='Computer Science',
                    year='Junior'
                )
                test_user.set_password('password123')
                db.session.add(test_user)
                
                # Create another test user for messaging
                second_user = User(
                    student_id='jane@university.edu',
                    name='Jane Smith',
                    major='Biology',
                    year='Senior'
                )
                second_user.set_password('password123')
                db.session.add(second_user)
                
                # Create additional test users
                additional_users = [
                    User(
                        student_id='alex@university.edu',
                        name='Alex Johnson',
                        major='Engineering',
                        year='Sophomore'
                    ),
                    User(
                        student_id='michael@university.edu',
                        name='Michael Brown',
                        major='Business',
                        year='Senior'
                    ),
                    User(
                        student_id='sarah@university.edu',
                        name='Sarah Wilson',
                        major='Psychology',
                        year='Junior'
                    ),
                    User(
                        student_id='david@university.edu',
                        name='David Lee',
                        major='Mathematics',
                        year='Freshman'
                    ),
                    User(
                        student_id='emily@university.edu',
                        name='Emily Chen',
                        major='Art History',
                        year='Senior'
                    )
                ]
                
                for user in additional_users:
                    user.set_password('password123')
                    db.session.add(user)
                
                # Add test announcements
                announcements = [
                    Announcement(
                        title='Welcome to the New Semester',
                        content='Welcome back to campus! We hope you had a great summer break. Classes begin on Monday.',
                        type='normal',
                        date=datetime.utcnow()
                    ),
                    Announcement(
                        title='Library Hours Extended',
                        content='The university library will now be open until midnight on weekdays to accommodate study groups.',
                        type='normal',
                        date=datetime.utcnow()
                    ),
                    Announcement(
                        title='Campus Safety Alert',
                        content='Due to ongoing construction, the north entrance will be closed until further notice. Please use the east or west entrances.',
                        type='urgent',
                        date=datetime.utcnow()
                    )
                ]
                
                for announcement in announcements:
                    db.session.add(announcement)
                
                # Add test news
                news_items = [
                    News(
                        title='University Team Wins National Championship',
                        content='Our university basketball team has won the national championship for the third year in a row! Congratulations to all players and coaches.',
                        category='Sports',
                        date=datetime.utcnow()
                    ),
                    News(
                        title='New Research Grant Awarded',
                        content='The Science Department has been awarded a $2 million grant for climate research. This will fund new equipment and graduate positions.',
                        category='Academic',
                        date=datetime.utcnow()
                    ),
                    News(
                        title='Student Art Exhibition Opens',
                        content='The annual student art exhibition opens this Friday in the Arts Building. All students and faculty are invited to attend.',
                        category='Arts',
                        date=datetime.utcnow()
                    )
                ]
                
                for news_item in news_items:
                    db.session.add(news_item)
                
                # Add test clubs
                clubs = [
                    Club(
                        name='Coding Club',
                        description='A club for students interested in programming, web development, and software engineering. We host weekly coding sessions and hackathons.'
                    ),
                    Club(
                        name='Debate Society',
                        description='Join us to improve your public speaking and critical thinking skills. We participate in regional and national debate competitions.'
                    ),
                    Club(
                        name='Environmental Action',
                        description='Dedicated to promoting sustainability on campus and in the community. We organize clean-ups, awareness campaigns, and sustainability projects.'
                    ),
                    Club(
                        name='Chess Club',
                        description='For beginners and masters alike. We meet every Tuesday evening in the Student Center for games and strategy discussions.'
                    )
                ]
                
                for club in clubs:
                    db.session.add(club)
                
                # Add test events
                from datetime import timedelta
                
                # Future events
                future_events = [
                    Event(
                        title='Freshman Orientation',
                        description='Welcome event for all new students. Campus tour, information sessions, and meet & greet with faculty.',
                        date=datetime.utcnow() + timedelta(days=5),
                        location='Student Center'
                    ),
                    Event(
                        title='Career Fair',
                        description='Annual career fair with over 50 companies recruiting for internships and full-time positions.',
                        date=datetime.utcnow() + timedelta(days=15),
                        location='University Hall'
                    ),
                    Event(
                        title='Coding Workshop',
                        description='Learn the basics of Python programming in this hands-on workshop. No prior experience required.',
                        date=datetime.utcnow() + timedelta(days=7),
                        location='Computer Science Building, Room 101'
                    )
                ]
                
                for event in future_events:
                    db.session.add(event)
                
                # Past events
                past_events = [
                    Event(
                        title='Alumni Networking Night',
                        description='Connect with successful alumni from various industries and learn about career opportunities.',
                        date=datetime.utcnow() - timedelta(days=10),
                        location='University Club'
                    ),
                    Event(
                        title='Spring Concert',
                        description='Annual spring concert featuring student bands and special guest performers.',
                        date=datetime.utcnow() - timedelta(days=30),
                        location='Outdoor Amphitheater'
                    )
                ]
                
                for event in past_events:
                    db.session.add(event)
                
                # Add test messages between users
                messages = [
                    Message(
                        sender_id=1,
                        receiver_id=2,
                        content='Hi Jane, do you have the notes from yesterday\'s lecture?',
                        timestamp=datetime.utcnow() - timedelta(days=2, hours=3),
                        is_read=True
                    ),
                    Message(
                        sender_id=2,
                        receiver_id=1,
                        content='Yes, I do! I\'ll send them to you after class today.',
                        timestamp=datetime.utcnow() - timedelta(days=2, hours=2),
                        is_read=True
                    ),
                    Message(
                        sender_id=1,
                        receiver_id=2,
                        content='Thanks! Are you going to the study group tonight?',
                        timestamp=datetime.utcnow() - timedelta(days=1, hours=5),
                        is_read=True
                    ),
                    Message(
                        sender_id=2,
                        receiver_id=1,
                        content='I\'m planning to. It starts at 7pm in the library, right?',
                        timestamp=datetime.utcnow() - timedelta(days=1, hours=4),
                        is_read=False
                    ),
                    Message(
                        sender_id=1,
                        receiver_id=2,
                        content='Yes, 7pm in the library, room 202. See you there!',
                        timestamp=datetime.utcnow() - timedelta(hours=12),
                        is_read=False
                    )
                ]
                
                for message in messages:
                    db.session.add(message)
                
                # Make sure to commit all changes
                db.session.commit()
                print("Test data created successfully!")
            else:
                print("Database already contains data, skipping test data creation.")
        else:
            print("Database already contains data, skipping test data creation.")
    
    # Start the Flask development server
    app.run(debug=True)
