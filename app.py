from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import random
import math
import os   
import psycopg2
import schedule
from time import sleep
import time
from psycopg2.extras import DictCursor
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from faker import Faker
import random
from operator import itemgetter
import portalocker

# timezone
JST = pytz.timezone('Asia/Tokyo')


# deploy on heroku
# DATABASE_URL = os.environ['DATABASE_URL']

#local deploy

#login info
your_username = "postgres"
your_port = "5432"
your_database_name = "postgres"
your_host = "localhost"
your_password = "B2s7I2i9"
DATABASE_URL = f"postgresql://{your_username}:{your_password}@{your_host}:{your_port}/{your_database_name}?sslmode=disable"

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッションを使用するための秘密鍵を設定

# connect to database
def connect_to_database():
    conn = psycopg2.connect(DATABASE_URL, sslmode='disable')
    return conn

#configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# login required decorator
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# each route 
# index route
@app.route("/")
@login_required
def index():
    # show users goal
    user_id = session["user_id"]

    # get the user's goal from database
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
                goal = cur.fetchone()         
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")

    # get the user's deadline from database
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT deadline FROM rooms WHERE user_id = %s", (user_id,))
                deadline = cur.fetchone()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    # get the user's username from database
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                username = cur.fetchone()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    if not goal:
        return render_template("index.html", username=username["name"])
    
    elif not deadline:
        return render_template("index.html", goal=goal["goal"], username=username["name"])
    
    else:
        return render_template("index.html", goal=goal["goal"], username=username["name"], deadline=deadline["deadline"])
    
# login route
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()

    # When POST
    if request.method == "POST":
        # get the user's input
        username = request.form.get("username")
        password = request.form.get("password")

        # When invalid input
        if not username:
            return render_template("apology.html", msg="ユーザーネームを入力してください")

        elif not password:
            return render_template("apology.html", msg="パスワードを入力してください")

        # Get imput username from database
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM users WHERE name = %s", (username,))
                    user = cur.fetchone()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        # Check the username and password are correct
        if not user or not check_password_hash(user["password_hash"], password):
            return render_template("apology.html", msg="不当なユーザーネームまたはパスワードです")

        # All OK add user to session
        session["user_id"] = user["id"]

        # Redirect user to home page
        return redirect("/")

    # When GET
    else:
        return render_template("login.html")
    
# logout route
@app.route("/logout")
def logout():
    """Log user out"""
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# register route
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
     # When POST
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        user_type = request.form.get("usertype")

        # Ensure username was submitted
        if not username:
            return render_template("apology.html", msg="ユーザーネームを入力してください")

        # Ensure password was submitted
        elif not password:
            return render_template("apology.html", msg="パスワードを入力してください")

        # Ensure password was submitted again
        elif not confirmation:
            return render_template("apology.html", msg="パスワードを再度入力してください")

        # password matches confirmation
        elif password != confirmation:
            return render_template("apology.html", msg="パスワードを正しく入力してください")
        
        # Ensure user type was submitted
        elif not user_type:
            return render_template("apology.html", msg="ユーザータイプを選択してください")

        # Check the username already exists
        # Query database for username
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM users WHERE name = %s", (username,))
                    user = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        if  len(user) != 0:
            return render_template("apology.html", msg="そのユーザーネームはすでに使われています")

        else:
            # Insert username and password hash to table
            password_hash = generate_password_hash(password)
            try:
                with connect_to_database() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO users (name, password_hash, type) VALUES (%s, %s, %s)", (username, password_hash, user_type))
                    conn.commit()
            except Exception as e:
                print(e)
                return render_template("apology.html", msg="失敗しました")

            # redirect log in page
            return redirect("/")

    else:
        return render_template("register.html")
    
# make_room route
@app.route("/make_room", methods=["GET", "POST"])
@login_required
def make_room():
    """Make Room"""
    # get the user's id
    user_id = session["user_id"]

    # When POST
    if request.method == "POST":
        
        # get the user's input
        room_id = int(request.form.get("room_id"))
        room_password = request.form.get("password")
        date = request.form.get("date")
        time = request.form.get("time")

        deadline = datetime.strptime(date + " " + time, '%Y-%m-%d %H:%M')

        # When invalid input
        if not room_id or not room_password or not date or not time:
            return render_template("apology.html", msg="正しく入力してください")
        
        # when room id is mainus or not integer, return apology
        if room_id < 0:
            return render_template("apology.html", msg="ルームIDは正の整数を入力してください")
        
        # if the room id already exists, return apology
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM rooms WHERE room_id = %s", (room_id,))
                    room = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")

        if len(room) != 0:
            return render_template("apology.html", msg="そのルームIDはすでに使われています")

        # password to hash
        room_password_hash = generate_password_hash(room_password)

        # Put room info to database        
        try:
            with connect_to_database() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO rooms (room_id, room_password_hash, user_id, deadline) VALUES (%s, %s, %s, %s)", (room_id, room_password_hash, user_id, deadline))
                conn.commit()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        return redirect("/enter_room")
    

    # When GET
    else:
        # if user already join a room, tell it
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM rooms WHERE user_id = %s", (user_id,))
                    room = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        if len(room) != 0:
            return render_template("make_room.html", msg="すでにルームに参加しています")
        
        # check user submit goal
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
                    goal = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")

        if len(goal) == 0:
            return render_template("apology.html", msg="目標を設定してください")
        
        else:
            today = datetime.now(JST).date()
            return render_template("make_room.html", today=today)
    
# enter room route
@app.route("/enter_room", methods=["GET", "POST"])
@login_required
def enter_room():
    """enter room"""
    # get the user's id
    user_id = session["user_id"]

    # When POST
    if request.method == "POST":
        # get the user's input
        room_id = int(request.form.get("room_id"))
        room_password = request.form.get("password")
        
        # When invalid input
        if not room_id or not room_password:
            return render_template("apology.html", msg="ルームIDとパスワードを入力してください")
        
        # when room id is mainus, return apology
        if room_id < 0:
            return render_template("apology.html", msg="ルームIDは正の整数を入力してください")
        
        # check user submit goal
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
                    goal = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")

        if len(goal) == 0:
            return render_template("apology.html", msg="目標を設定してください")
        
        # Get room info from database
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM rooms WHERE room_id = %s", (room_id,))
                    room = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        # get the room's deadline
        deadline = room[0]["deadline"]

        # Check the room id and password are correct
        if len(room) == 0 or not check_password_hash(room[0]["room_password_hash"], room_password):
            return render_template("apology.html", msg="不当なルームIDまたはパスワードです")
        
        else:
            #パスワードをハッシュ化
            room_password_hash = generate_password_hash(room_password)
            # ユーザーを部屋に追加
            try:
                with connect_to_database() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO rooms (room_id, room_password_hash, user_id, deadline) VALUES (%s, %s, %s, %s)", (room_id, room_password_hash, user_id, deadline))
                    conn.commit()
            except Exception as e:
                print(e)
                return render_template("apology.html", msg="失敗しました")
            
            return redirect(url_for("room", room_id=room_id))
        
    # When GET
    else:
        """if user already join a room, redirect to room page"""
        # get the user's id
        user_id = session["user_id"]

        # check user submit goal
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
                    goal = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")

        if len(goal) == 0:
            return render_template("apology.html", msg="目標を設定してください")

        # get the user's room info from database
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM rooms WHERE user_id = %s", (user_id,))
                    room = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")

        # if user already join a room, redirect to room page
        if len(room) != 0:
            return redirect(url_for("room", room_id=room[0]["room_id"]))
        
        else:
            return render_template("enter_room.html")
    
# room route
@app.route("/room")
@login_required
def room():
    user_id = session["user_id"]
    room_id = int(request.args.get("room_id"))

    #if the room does not exist, return apology
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM rooms WHERE room_id = %s", (room_id,))
                room = cur.fetchall()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")

    if len(room) == 0:
        return render_template("apology.html", msg="そのルームは存在しません")

    # if the user does not join the room, return apology
    room_users_ids = []
    for room_user in room:
        room_users_ids.append(room_user["user_id"])

    if user_id not in room_users_ids:
        return render_template("apology.html", msg="このルームに参加していません")
    
    goals = []
    # get all menbers' goal info
    for room_user_id in room_users_ids:
        # 各user_idごとの目標と進捗率を取得し、辞書に追加
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM goals WHERE user_id = %s", (room_user_id,))
                    user_goals = cur.fetchall()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        # get user's name
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM users WHERE id = %s", (room_user_id,))
                    username = cur.fetchone()["name"]
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        # add username and goal info to user_goals
        user_goal_dicts = [{"goal": goal["goal"], "progress_rate": goal["progress_rate"], "user_id": goal["user_id"], "username": username} for goal in user_goals]
        goals.extend(user_goal_dicts)
    
    # get all members' username
    usernames = []
    for room_user_id in room_users_ids:
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM users WHERE id = %s", (room_user_id,))
                    username = cur.fetchone()["name"]
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        usernames.append(username)
    
    #shuffle usernames and goals
    random.shuffle(usernames)
    random.shuffle(goals)
    
    # get the number of members
    number_of_members = len(usernames)

    # get progress rate average
    progress_rate_sum = 0
    for goal in goals:
        progress_rate_sum += goal["progress_rate"]
    progress_rate_average = progress_rate_sum / number_of_members  
    average = math.floor(progress_rate_average)

    # get room's deadline 
    deadline = room[0]["deadline"]

    # each user type has different room page
    # get user type
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT type FROM users WHERE id = %s", (user_id,))
                user_type = cur.fetchone()["type"]
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    # if user is positive, return positive room page
    if user_type == "positive":
        return render_template("positive_room.html", goals=goals, user_id=user_id, number_of_members=number_of_members, average=average, deadline=deadline)
    
    # if user is sensitive, return sensitive room page
    elif user_type == "sensitive":
        return render_template("room.html", goals=goals, usernames=usernames, user_id=user_id, number_of_members=number_of_members, average=average, deadline=deadline)

    # if user is negative, return negative room page
    else:
        return render_template("negative_room.html", goals=goals, user_id=user_id, number_of_members=number_of_members, average=average, deadline=deadline)


# leave room route
@app.route("/leave_room", methods=["POST"])
@login_required
def leave_room():
    """leave room"""
    # get the user's id
    user_id = session["user_id"]

    # delete user from room
    try:
        with connect_to_database() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rooms WHERE user_id = %s", (user_id,))
            conn.commit()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    return redirect("/enter_room")
    
# goal route
@app.route("/goal", methods=["GET", "POST"])
@login_required
def goal():
    """goal"""
    # Get user's id
    user_id = session["user_id"]

    # When POST
    if request.method == "POST":
        # get the user's goal input
        final_goal = request.form.get("final_goal")
        minimum_goal = request.form.get("goal")

        # When invalid input
        if not minimum_goal or not final_goal:
            return render_template("apology.html", msg="正しく入力してください")

        # date created
        date_created = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')

        # goal = final_goal + minimum_goal
        goal = final_goal + "ために、" + minimum_goal + "!"

        # Put goal info to database
        # put into goals table
        try:
            with connect_to_database() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO goals (goal, date_created, user_id) VALUES (%s, %s, %s)", (goal, date_created, user_id))
                conn.commit()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        # put into goals_history table
        default_progress_rate = 0
        try:
            with connect_to_database() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO goals_history (goal, user_id, progress_rate, date_created) VALUES (%s, %s, %s, %s)", (goal, user_id, default_progress_rate, date_created))
                conn.commit()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")
        
        return redirect("/goal")

    # When GET
    else:
        # if user already has a goal, display it
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
                    goal = cur.fetchall()
                    cur.execute("SELECT * FROM rooms WHERE user_id = %s", (user_id,))
                    deadline = cur.fetchone()
        except Exception as e:
            print(e)
            return render_template("apology.html", msg="失敗しました")

        today = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
        
        if not goal:
            return render_template("goal.html", today=today)
        
        elif not deadline== 0:
            return render_template("goal.html", goal=goal[0]["goal"], id=goal[0]["id"], progress_rate=goal[0]["progress_rate"], today=today)
        else:
            return render_template("goal.html", goal=goal[0]["goal"], id=goal[0]["id"], progress_rate=goal[0]["progress_rate"], today=today, deadline=deadline["deadline"])
        
# delete goal route
@app.route("/delete_goal", methods=["POST"])
@login_required
def delete_goal():
    """delete goal"""

    # get user id
    user_id = session["user_id"]

    # delete goal from database    
    try:
        with connect_to_database() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM goals WHERE user_id = %s", (user_id,))
            conn.commit()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    return redirect("/goal")

# update progress rate route
@app.route("/update_progress_rate", methods=["POST"])
@login_required
def update_progress_rate():
    """update progress rate"""
    # get user id
    user_id = session["user_id"]

    # get room id user in
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM rooms WHERE user_id = %s", (user_id,))
                room = cur.fetchall()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")

    # get progress rate
    progress_rate = int(request.form.get("progress"))

    # update progress rate
    # update goals table
    try:
        with connect_to_database() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE goals SET progress_rate = %s WHERE user_id = %s", (progress_rate, user_id))
            conn.commit()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    # update goals_history table, but only date_created is newest one
    try:
        with connect_to_database() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE goals_history SET progress_rate = %s WHERE user_id = %s AND date_created = (SELECT MAX(date_created) FROM goals_history WHERE user_id = %s)", (progress_rate, user_id, user_id))
            conn.commit()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    # if user in a room, redirect to room page
    if len(room) != 0:
        return redirect(url_for("room", room_id=room[0]["room_id"]))
    
    # if user not in a room, redirect to goal page
    else:
        return redirect("/goal")
    
# notion route
@app.route("/notion")
@login_required
def notion():
    """notion"""
    return render_template("notion.html")

# profile route
@app.route("/profile")
@login_required
def profile():
    """profile"""
    # get user id
    user_id = session["user_id"]

    # get username and user type
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                username = cur.fetchone()["name"]
    except Exception as e:
        print(e)
        return render_template("apology.html", msg=str(e))

    # get user's goal history
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM goals_history WHERE user_id = %s", (user_id,))
                goals_history = cur.fetchall()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg=str(e))

    return render_template("profile.html", username=username, goals_history=goals_history)


# cheer route
@app.route("/cheer", methods=["POST"])
def cheer():
    # get user id
    user_id = session["user_id"]

    # get room id user in and username
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM rooms WHERE user_id = %s", (user_id,))
                room_id = cur.fetchone()["room_id"]
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
    # send line message to the room members
    # get line user ids in the room
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT line_user_id FROM line_users WHERE room_id = %s", (room_id,))
                line_user_ids = [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")
    
        
    # send message to the line users
    for line_user_id in line_user_ids:
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=f"あなたがちゃんとやっているか、気にしている人がいます！進捗を報告してあげましょう！ {APP_URL}")
        )

    return redirect(url_for("room", room_id=room_id))

# delete goal and room function
def delete_goal_and_room():
    # get date
    today = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')

    # delete room deadline which is earlier than today and delete the room members goal 
    try:
        with connect_to_database() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM goals WHERE id IN (SELECT id FROM goals WHERE user_id IN (SELECT user_id FROM rooms WHERE deadline < %s))", (today,))
                cur.execute("DELETE FROM rooms WHERE deadline < %s", (today,))
            conn.commit()
    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")

@app.route("/progress_ranking")
@login_required
def progress_ranking():
    """Display progress ranking"""
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Get all users' progress rates along with their usernames
                cur.execute("""
                    SELECT users.name, goals.progress_rate 
                    FROM goals 
                    JOIN users ON goals.user_id = users.id 
                    ORDER BY goals.progress_rate DESC
                """)
                rankings = cur.fetchall()

    except Exception as e:
        print(e)
        return render_template("apology.html", msg="失敗しました")

    # Render the rankings in the template, passing the enumerate function　←enumerateを追加
    return render_template("ranking.html", rankings=rankings, enumerate=enumerate)



@app.route("/dummy_progress_ranking")
@login_required
def dummy_progress_ranking():
    """Display dummy progress ranking"""
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # 本物のユーザーの進捗率を取得
                cur.execute("""
                    SELECT users.name, goals.progress_rate 
                    FROM goals 
                    JOIN users ON goals.user_id = users.id 
                    ORDER BY goals.progress_rate DESC
                """)
                real_users_rankings = cur.fetchall()

                 # セッションからダミーデータを取得
                if 'dummy_data' not in session:
                    # ニックネームリストを作成
                    nicknames = [
                    "山田 太郎", "佐藤 花子", "鈴木 一郎", "高橋 美咲", "田中 健太", "伊藤 純子", 
                    "渡辺 明", "中村 真由美", "小林 正人", "加藤 里奈", "松本 拓也", "藤田 優子", 
                    "斉藤 直樹", "岡田 さゆり", "村上 健司", "近藤 美和", "石川 悠太", "長谷川 美紀", 
                    "木村 大輔", "林 千尋", "池田 翔", "橋本 梨花", "山口 剛", "清水 あかり", "森 大地", 
                    "浅野 亮介", "原 友里", "河野 亮", "松井 愛美"
                    ] 

                    # 0から100の間のランダムな進捗率を生成し、ダミーデータを生成
                    dummy_data = [{'name': random.choice(nicknames), 'progress_rate': random.randint(0, 100)} for _ in range(10)]
                    
                    # セッションに保存
                    session['dummy_data'] = dummy_data
                else:
                    # セッションからダミーデータを取得
                    dummy_data = session['dummy_data']

                # 本物のユーザーとダミーユーザーを含むランキングリストを作成
                combined_rankings = real_users_rankings + dummy_data

                # 進捗率でランキングリストを降順にソート
                combined_rankings.sort(key=lambda x: x['progress_rate'], reverse=True)

                # ランクを付ける
                rankings_with_ranks = [
                    {'name': user['name'], 'progress_rate': user['progress_rate'], 'rank': index + 1}
                    for index, user in enumerate(combined_rankings)
                ]
               
                # # 順位を付ける
                # rankings_with_ranks = [
                #     {'name': row[0], 'progress_rate': row[1], 'rank': index + 1}
                #     for index, row in enumerate(rankings)
                # ]
                
                # 0から100の間のランダムな進捗率を生成し、ダミーデータを生成
                #dummy_data = [{'name': random.choice(nicknames), 'progress_rate': random.randint(0, 100)} for _ in range(100)]

                # 本物のユーザーとダミーユーザーを含むランキングリストを作成
                #combined_rankings = real_users_rankings + dummy_data

                # 進捗率でランキングリストを降順にソート
                #combined_rankings.sort(key=itemgetter('progress_rate'), reverse=True)

                # ランクを付ける
                #for i, user in enumerate(combined_rankings, start=1):
                #    user['rank'] = i

                # デバッグ用ログを追加
                #for user in combined_rankings:
                #    print(f"Rank: {user['rank']}, Name: {user['name']}, Progress Rate: {user['progress_rate']}")

                # ニックネームをランダムに選んでダミーデータを生成
                #dummy_data = [{'name': random.choice(nicknames), 'progress_rate': random_progress_rate} for _ in range(100)]
                
                # Fakerライブラリを使用して日本人の名前のダミーデータを生成
                # fake = Faker('ja_JP')
                # dummy_data = [{'name': fake.name(), 'progress_rate': random_progress_rate} for _ in range(100)]


                # ランキングリストの最後にダミーデータを追加
                #rankings.extend(dummy_data)

    except Exception as e:
        # Log the exception (具体的なログ方法はログライブラリに依存)
        print(f"Error: {e}")
        return render_template("apology.html", msg="失敗しました")

    # Render the rankings in the template, passing the enumerate function　←enumerateを追加
    return render_template("dummy_ranking.html", rankings=rankings_with_ranks, enumerate=enumerate)

@app.route("/clear_dummy_data")
@login_required
def clear_dummy_data():
    """Clear dummy data from session"""
    session.pop('dummy_data', None)  # 'dummy_data'キーを削除、キーが存在しない場合は何もしない
    return redirect(url_for('dummy_progress_ranking'))  # ランキングページにリダイレクト

@app.route("/clear_all_sessions")
@login_required
def clear_all_sessions():
    """Clear all session data"""
    session.clear()  # 全てのセッションデータを削除
    return redirect(url_for('dummy_progress_ranking'))  # ランキングページにリダイレクト




    
# linebot 
#Token取得


"""
# 本番環境
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["CHANNEL_SECRET"]

# アプリのURL
APP_URL = "https://pot-of-goald-f14a2468eebb.herokuapp.com/"

line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

# Webhook
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# Message handler
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # get line user id
    line_user_id = event.source.user_id

    # line menu message
    # 部屋を登録
    if event.message.text == "部屋を登録":
        # 既に部屋に登録されているか確認
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM line_users WHERE line_user_id = %s", (line_user_id,))
                    line_user = cur.fetchall()
        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました")
            )

        # 既に部屋に登録されている場合、部屋を解除してくださいと返信
        if len(line_user) != 0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="部屋を解除してください")
            )

        # 部屋に登録されていない場合、部屋番号を入力してくださいと返信
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="部屋番号を数字のみ入力してください")
            )

    if event.message.text == "登録を解除":
        # 既に部屋に登録されているか確認
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM line_users WHERE line_user_id = %s", (line_user_id,))
                    line_user = cur.fetchall()
        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました")
            )

        # 既に部屋に登録されている場合、部屋を解除
        if len(line_user) != 0:
            try:
                with connect_to_database() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM line_users WHERE line_user_id = %s", (line_user_id,))
                    conn.commit()
            except Exception as e:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="エラーが発生しました")
                )
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="部屋を解除しました")
            )
        
        # 部屋に登録されていない場合、部屋を登録してくださいと返信
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="部屋を登録してください")
            )

    
    # 正の整数が入力されたとき
    if event.message.text.isdigit():
        line_user_id = event.source.user_id
        room_id = int(event.message.text)

        # 有効な部屋番号か確認
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM rooms WHERE room_id = %s", (room_id,))
                    room = cur.fetchall()
        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました")
            )

        # 無効な部屋番号の場合
        if len(room) == 0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="無効な部屋番号です")
            )
        
        # 既に部屋に登録されているか確認
        try:
            with connect_to_database() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM line_users WHERE line_user_id = %s", (line_user_id,))
                    line_user = cur.fetchall()
        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました")
            )

        
        # 部屋に登録されていない場合、部屋を登録
        if len(line_user) == 0:
            try:
                with connect_to_database() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO line_users (line_user_id, room_id) VALUES (%s, %s)", (line_user_id, room_id))
                    conn.commit()
            except Exception as e:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="エラーが発生しました")
                )
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="部屋番号を登録しました")
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="部屋を解除してください")
            )

    # ランキング
    if event.message.text == "ランキング":
        # get line user id
        line_user_id = event.source.user_id

        # push message to the line user
        push_progress_message(line_user_id)
    
    # 使い方
    if event.message.text == "使い方":
        how_to_use_text = "部屋を登録：参加中のルームIDを入力して部屋を登録します\n登録を解除：登録している部屋を解除して、新たな部屋を登録します。\nランキング：部屋に参加しているメンバーの目標達成率ランキングを表示します\n使い方：使い方を表示します\nやる気がなくなった：やる気がなくなったときのヒントを表示します\nアプリ：アプリへ移動します"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=how_to_use_text)
        )
    
    # やる気がなくなったとき用のヒント
    TIPS = ["目標が難しすぎると、やる気がなくなります。目標を小さく設定してみましょう。",
            "ポモドーロテクニックを試してみましょう。25分間集中して作業し、5分間休憩します。これを繰り返します。",
            "目標を達成するためには、習慣化が必要です。毎日少しずつでも続けてみましょう。",
            "何のために目標を設定したのか、最終的な目標は何かを思い出しましょう。",
            "目標を達成することがどう自分の人生に影響するかを考えてみましょう。"
            ]

    # やる気がなくなった
    if event.message.text == "やる気がなくなった":
        # ランダムにヒントを表示
        tip = random.choice(TIPS)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=tip)
        )

    # else
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="個別のメッセージには対応していません。使い方を参考に、メニュー画面を操作してください。")
        )

# Push message to the line users
def push_progress_message(line_user_id):
    # where user in a room latest one
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM line_users WHERE line_user_id = %s", (line_user_id,))
                line_user = cur.fetchall()
    except Exception as e:
        # send error to the line user
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=f"エラーが発生しました")
        )
    
    # get goals and progress rate in the room, and sort by progress rate
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT user_id FROM rooms WHERE room_id = %s", (line_user[0]["room_id"],))
                user_ids = [row[0] for row in cur.fetchall()]
    except Exception as e:
        # send error to the line user
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=f"エラーが発生しました")
        )

    # get goals and progress rate in the room, and sort by progress rate
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM goals WHERE user_id IN %s ORDER BY progress_rate DESC", (tuple(user_ids),))
                users_goals_info = cur.fetchall()
    except Exception as e:
        # send error to the line user
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=f"エラーが発生しました")
        )

    # count the number of members
    number_of_members = len(users_goals_info)

    # push message to the line user
    try:
        # send members' goals and progress rate to the line user
        message = f"現在のランキングをお知らせします\n\n"
        for i in range(number_of_members):
            message += f"{i+1}位：{users_goals_info[i]['goal']} {users_goals_info[i]['progress_rate']}%\n"
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=message)
        )        

    except Exception as e:
        # send error to the line user
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=f"エラーが発生しました")
        )
     
# scheduled message to the line users
def schedule_message():
    # get all line users
    try:
        with connect_to_database() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT * FROM line_users")
                line_users = cur.fetchall()
    except Exception as e:
        return str(e)


    # set random encouragement message
    ENCOUAGEMENT_MESSAGES = ["ちゃんと目標達成に向かって頑張っていますか？", 
                             "目標達成に向けて真剣に取り組んでいますか？", 
                             "着実に目標達成に向けて進んでいますか？", 
                             "自分で宣言したことを守れていますか？", 
                             "コツコツと目標達成のために努力できていますか？", 
                             "目標達成に集中できていますか？", 
                             "自分で宣言した目標を意識できていますか？",
                             "努力を継続できていますか？",
                             "最終目標を意識して、努力できていますか？",
                             "誘惑に負けずに、努力できていますか？",]
    
    # push message to the line users
    for line_user in line_users:
        # set random encouragement message
        encouragement_message = random.choice(ENCOUAGEMENT_MESSAGES)

        # push message to the line user
        try:
            line_bot_api.push_message(
                line_user["line_user_id"],
                TextSendMessage(text=encouragement_message + f" {APP_URL}")
            )
        except Exception as e:
            return str(e)

# scheduled message to the line users
sched = BackgroundScheduler(daemon=True)
sched.add_job(schedule_message, 'cron', hour=20, minute=0, timezone=JST)
sched.add_job(delete_goal_and_room, 'interval', minutes=1, timezone=JST)
sched.start()
"""

# run app
if __name__ == "__main__":
    app.run()