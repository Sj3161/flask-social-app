from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from math import radians, cos, sin, asin, sqrt
import json

app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'

db = SQLAlchemy(app)
from flask_migrate import Migrate
migrate = Migrate(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    latitude = db.Column(db.Float, default=12.9716)
    longitude = db.Column(db.Float, default=77.5946)
    mute_messages = db.Column(db.Boolean, default=False)
    mute_posts = db.Column(db.Boolean, default=False)
    mute_requests = db.Column(db.Boolean, default=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    visibility = db.Column(db.String(10), nullable=False, default='public')
    friend_ids = db.Column(db.Text, default='[]')
    tag = db.Column(db.String(50), default='general')
    is_anonymous = db.Column(db.Boolean, default=False)


class PrivateGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    type = db.Column(db.String(50), default='general')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(255))
    seen = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    type = db.Column(db.String(50), default='general')  # Add this line



with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE notification ADD COLUMN type VARCHAR(50) DEFAULT 'general';"))
            print("✅ 'type' column added to Notification table.")
    except Exception as e:
        print("⚠️ Error or already exists:", e)

    # To check columns
    with db.engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(post);"))
        for row in result:
            print(row)



def within_10km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c <= 10

def send_notification(user_id, message, notif_type='general'):
    user = User.query.get(user_id)
    if notif_type == 'message' and user.mute_messages:
        return
    if notif_type == 'post' and user.mute_posts:
        return
    if notif_type == 'friend_request' and user.mute_requests:
        return

    notification = Notification(user_id=user_id, message=message, type=notif_type)
    db.session.add(notification)
    db.session.commit()



@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("This user no longer exists.", "danger")
            return redirect(url_for("login"))
        if check_password_hash(user.password, password):
            session['user_id'] = user.id
            session.modified = True
            flash('Login successful!', 'success')
            return redirect(url_for('inner_home'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            flash('Email or username already exists.', 'danger')
            return redirect(url_for('signup'))
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Signup successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/inner_home', methods=['GET'])
def inner_home():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    lat = float(request.args.get('lat', user.latitude))
    lon = float(request.args.get('lon', user.longitude))
    user.latitude = lat
    user.longitude = lon
    db.session.commit()

    blocked_usernames = session.get('blocked_users', [])

    all_posts = Post.query.all()
    visible_posts = []
    for post in all_posts:
        post_user = db.session.get(User, post.user_id)
        if post.username in blocked_usernames:
            continue
        if post.visibility == 'public':
            if within_10km(lat, lon, post_user.latitude, post_user.longitude):
                visible_posts.append(post)
        elif post.visibility == 'private':
            allowed_friends = json.loads(post.friend_ids)
            if user.id == post.user_id or user.id in allowed_friends:
                visible_posts.append(post)

    friend_links = Friend.query.filter_by(user_id=user.id).all()
    friend_ids = [f.friend_id for f in friend_links]

    received_requests = FriendRequest.query.filter_by(receiver_id=user.id, status='pending').all()
    sent_requests = FriendRequest.query.filter_by(sender_id=user.id, status='pending').all()

    confirmed_friends = User.query.filter(User.id.in_(friend_ids)).all()

    excluded_ids = (
            friend_ids +
            [r.receiver_id for r in sent_requests if r.status == 'pending'] +
            [r.sender_id for r in received_requests if r.status == 'pending']
    )

    all_users = User.query.filter(User.id != user.id, ~User.id.in_(excluded_ids)).all()
    sent_receiver_map = {u.id: u for u in User.query.filter(User.id.in_([r.receiver_id for r in sent_requests])).all()}

    print("🚨 DEBUG: Number of posts being passed to template =", len(visible_posts))

    return render_template(
        'inner_home.html',
        posts=visible_posts,
        username=user.username,
        friends=all_users,
        friend_requests=received_requests,
        sent_requests=sent_requests,
        confirmed_friends=confirmed_friends,
        users={u.id: u for u in User.query.all()},
        sent_users=sent_receiver_map,
        blocked_usernames=blocked_usernames
    )

@app.route('/block/<username>')
def block_user(username):
    if 'user_id' not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for('login'))

    blocked = session.get('blocked_users', [])
    if username not in blocked:
        blocked.append(username)
        session['blocked_users'] = blocked
    flash(f"{username} has been blocked.", "info")
    return redirect(url_for('inner_home'))

@app.route('/unblock/<username>')
def unblock_user(username):
    if 'user_id' not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for('login'))

    blocked = session.get('blocked_users', [])
    if username in blocked:
        blocked.remove(username)
        session['blocked_users'] = blocked
    flash(f"{username} has been unblocked.", "info")
    return redirect(url_for('inner_home'))

@app.route('/post_message', methods=['POST'])
def post_message():
    if 'user_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))

    content = request.form.get('content')
    visibility = request.form.get('visibility')
    selected_friends = request.form.getlist('friends')
    tag = request.form.get('tag') or "general"
    is_anonymous = request.form.get('is_anonymous') == 'true'  # ✅ Add this line here

    friend_ids_json = json.dumps([int(fid) for fid in selected_friends]) if visibility == 'private' else '[]'

    user = db.session.get(User, session['user_id'])

    new_post = Post(
        content=content,
        username="Anonymous" if is_anonymous else user.username,  # 👈 conditionally set username
        user_id=user.id,
        visibility=visibility,
        friend_ids=friend_ids_json,
        tag=tag,
        is_anonymous=is_anonymous  # ✅ Pass to the model
    )

    db.session.add(new_post)
    db.session.commit()

    # Optional: Notify friends if tagged as emergency
    if tag == 'emergency':
        friend_links = Friend.query.filter_by(user_id=user.id).all()
        friend_ids = [f.friend_id for f in friend_links]
        for fid in friend_ids:
            friend = User.query.get(fid)
            if friend and within_10km(user.latitude, user.longitude, friend.latitude, friend.longitude):
                send_notification(fid, f"🚨 Emergency post from @{user.username}")

    flash("Post shared!", "success")
    return redirect(url_for('inner_home'))



@app.route('/send_request/<int:receiver_id>')
def send_request(receiver_id):
    if 'user_id' in session:
        sender_id = session['user_id']
        if sender_id != receiver_id:
            existing = FriendRequest.query.filter_by(sender_id=sender_id, receiver_id=receiver_id).first()
            already_friends = Friend.query.filter_by(user_id=sender_id, friend_id=receiver_id).first()

            if not existing and not already_friends:
                request_entry = FriendRequest(sender_id=sender_id, receiver_id=receiver_id)
                db.session.add(request_entry)
                db.session.commit()
                flash('Friend request sent!', 'success')
            elif already_friends:
                flash('You are already friends!', 'info')
            else:
                flash('Friend request already sent.', 'info')
    return redirect(url_for('inner_home'))

@app.route('/accept_request/<int:request_id>')
def accept_request(request_id):
    req = FriendRequest.query.get(request_id)
    if req and req.receiver_id == session['user_id']:
        req.status = 'accepted'
        db.session.add(Friend(user_id=req.receiver_id, friend_id=req.sender_id))
        db.session.add(Friend(user_id=req.sender_id, friend_id=req.receiver_id))
        db.session.commit()
        flash('Friend request accepted!', 'success')
    return redirect(url_for('inner_home'))

@app.route('/reject_request/<int:request_id>')
def reject_request(request_id):
    req = FriendRequest.query.get(request_id)
    if req and req.receiver_id == session['user_id']:
        req.status = 'rejected'
        db.session.commit()
        flash('Friend request rejected.', 'info')
    return redirect(url_for('inner_home'))

@app.route('/cancel_request/<int:request_id>')
def cancel_request(request_id):
    req = FriendRequest.query.get(request_id)
    if req and req.sender_id == session.get('user_id'):
        db.session.delete(req)
        db.session.commit()
        flash('Friend request cancelled.', 'info')
    return redirect(url_for('inner_home'))

@app.route('/unfriend/<int:friend_id>')
def unfriend(friend_id):
    user_id = session.get('user_id')
    if user_id:
        Friend.query.filter_by(user_id=user_id, friend_id=friend_id).delete()
        Friend.query.filter_by(user_id=friend_id, friend_id=user_id).delete()
        FriendRequest.query.filter(
            ((FriendRequest.sender_id == user_id) & (FriendRequest.receiver_id == friend_id)) |
            ((FriendRequest.sender_id == friend_id) & (FriendRequest.receiver_id == user_id))
        ).filter(FriendRequest.status == 'accepted').delete()

        db.session.commit()
        flash('Unfriended successfully.', 'info')
    return redirect(url_for('inner_home'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/confirm_delete')
def confirm_delete():
    if 'user_id' not in session:
        flash("Login required.", "danger")
        return redirect(url_for('login'))
    return render_template('delete_confirm.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/messages/<int:friend_id>', methods=['GET', 'POST'])
def private_chat(friend_id):
    if 'user_id' not in session:
        flash('Login required.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    friend = User.query.get_or_404(friend_id)

    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            new_msg = PrivateMessage(sender_id=user_id, receiver_id=friend_id, message=message)
            db.session.add(new_msg)
            db.session.commit()
            flash("Message sent!", "success")
        return redirect(url_for('private_chat', friend_id=friend_id))

    messages = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == user_id) & (PrivateMessage.receiver_id == friend_id)) |
        ((PrivateMessage.sender_id == friend_id) & (PrivateMessage.receiver_id == user_id))
    ).order_by(PrivateMessage.timestamp).all()

    return render_template('private_chat.html', friend=friend, messages=messages)

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        flash("Login required to delete account.", "danger")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    entered_password = request.form.get('password')

    if not user or not check_password_hash(user.password, entered_password):
        flash("Incorrect password. Account not deleted.", "danger")
        return redirect(url_for('confirm_delete'))

    user_id = user.id
    FriendRequest.query.filter((FriendRequest.sender_id == user_id) | (FriendRequest.receiver_id == user_id)).delete()
    Friend.query.filter((Friend.user_id == user_id) | (Friend.friend_id == user_id)).delete()
    Post.query.filter_by(user_id=user_id).delete()
    PrivateMessage.query.filter((PrivateMessage.sender_id == user_id) | (PrivateMessage.receiver_id == user_id)).delete()

    db.session.delete(user)
    db.session.commit()

    session.clear()
    flash("Your account has been permanently deleted.", "info")
    return redirect(url_for('home'))

@app.route('/notifications')
def get_notifications():
    if 'user_id' not in session:
        return jsonify([])
    user_id = session['user_id']
    notifs = Notification.query.filter_by(user_id=user_id, seen=False).order_by(Notification.timestamp.desc()).all()
    return jsonify([
        {"id": n.id, "message": n.message, "timestamp": n.timestamp.strftime('%Y-%m-%d %H:%M')}
        for n in notifs
    ])

@app.route('/notifications/seen', methods=['POST'])
def mark_notifications_seen():
    if 'user_id' not in session:
        return '', 401
    user_id = session['user_id']
    Notification.query.filter_by(user_id=user_id, seen=False).update({"seen": True})
    db.session.commit()
    return '', 204

with app.app_context():
    with db.engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(post);"))
        print("🔵 Columns in post table:")
        for row in result:
            print(row)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=True, host='0.0.0.0', port=port)
