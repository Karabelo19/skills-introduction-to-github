from flask import Flask, request, render_template, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import io
import base64
import itertools
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'super_secret_key'

# MySQL configuration
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="cold_room_db"
)
cursor = db.cursor(dictionary=True)


def insert_user(username, password, role):
    cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
    db.commit()

def validate_user(username, password, role):
    cursor.execute("SELECT * FROM users WHERE username = %s AND role = %s", (username, role))
    user = cursor.fetchone()
    if user:
        if user['password'] == password:
            return True
    return False


def store_sensor_data(data):
    query = """
        INSERT INTO sensor_data (temperature, humidity, ldr1, ldr2, pir, alert, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """
    cursor.execute(query, (
        data['temperature'],
        data['humidity'],
        data['ldr1'],
        data['ldr2'],
        data['pir'],
        data['alert']
    ))
    db.commit()

def get_sensor_data():
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 5")
    return cursor.fetchall()

def generate_pir_bar_plot():
    cursor.execute("SELECT pir, timestamp FROM sensor_data ORDER BY timestamp DESC LIMIT 20")
    rows = cursor.fetchall()
    rows.reverse()
    values = [int(row['pir']) for row in rows]
    times = [row['timestamp'].strftime('%H:%M:%S') for row in rows]

    plt.figure(figsize=(10, 3))
    colors = ['green' if v == 0 else 'red' for v in values]
    labels = ['No Motion' if v == 0 else 'Motion' for v in values]

    plt.bar(times, values, color=colors)
    plt.ylim(0, 1.5)
    plt.xticks(rotation=45)
    plt.ylabel("PIR Motion")
    plt.title("PIR Motion Detection (0: No Motion, 1: Motion)")
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8')


def generate_plot(sensor, label, color):
    cursor.execute(f"SELECT {sensor}, timestamp FROM sensor_data ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    if not rows:
        return ""  # No data yet

    rows.reverse()
    values = [row[sensor] for row in rows]
    times = [row['timestamp'].strftime('%H:%M:%S') for row in rows]

    plt.figure(figsize=(10, 4))
    plt.plot(times, values, color=color, label=label)
    plt.xticks(rotation=45)
    plt.xlabel("Time")
    plt.ylabel(label)
    plt.title(f"{label} Over Time")
    plt.grid(True)
    plt.tight_layout()
    plt.legend()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()  
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8')

# ---------- Routes ----------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Call your validate_user function
        result = validate_user(username, password, role)

        if result is True:
            session['username'] = username
            session['role'] = role
            return redirect(url_for(role))
        else:
            flash("Invalid credentials for selected role. Try again.", 'danger')

    return render_template('login.html')



@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Get sensor data
    sensor_data = get_sensor_data()
    if not sensor_data:
        flash("No sensor data found.", 'error')

    # Check alerts
    alerts = [f"Alert for {row['timestamp']}: {row['alert']}" for row in sensor_data if row['alert'] in ["High", "Low"]]
    combined_plot = "data:image/png;base64," + generate_combined_plot(sensor_data)

    cursor = db.cursor()
    cursor.execute("SELECT user_id, username, role FROM users WHERE role != 'admin'")
    users = cursor.fetchall()

    return render_template('admin.html', sensor_data=sensor_data, alerts=alerts, combined_plot=combined_plot, users=users, enumerate=enumerate)

def generate_combined_plot(sensor_data):
    if not sensor_data:
        return ""

    # Extract timestamps and individual sensor values
    timestamps = [row['timestamp'].strftime('%H:%M:%S') for row in sensor_data]
    temperature_values = [row['temperature'] for row in sensor_data]
    humidity_values = [row['humidity'] for row in sensor_data]
    ldr1_values = [row['ldr1'] for row in sensor_data]
    ldr2_values = [row['ldr2'] for row in sensor_data]
    pir_values = [row['pir'] for row in sensor_data]

    # Create the plot
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, temperature_values, color='red', label='Temperature (°C)')
    plt.plot(timestamps, humidity_values, color='blue', label='Humidity (%)')
    plt.plot(timestamps, ldr1_values, color='green', label='LDR Inside')
    plt.plot(timestamps, ldr2_values, color='orange', label='LDR Outside')
    plt.plot(timestamps, pir_values, color='purple', label='PIR Motion')

    plt.xticks(rotation=45)
    plt.xlabel('Time')
    plt.ylabel('Sensor Readings')
    plt.title('Smart Cold Room Sensor Data Over Time')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Convert the plot to PNG image
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)

    return base64.b64encode(img.getvalue()).decode('utf-8')

    

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        user_id = request.form['user_id']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        try:
            cursor.execute("INSERT INTO users (user_id, username, password, role) VALUES (%s, %s, %s, %s)",
                           (user_id, username, password, role))
            db.commit()
            flash("User added successfully!", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error adding user: {str(e)}", "error")

        return redirect(url_for('admin'))

    return render_template('add_user.html')


@app.route('/delete_user', methods=['GET', 'POST'])
def delete_user():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        
        try:
            cursor.execute("DELETE FROM users WHERE username = %s", (username,))
            if cursor.rowcount > 0:
                db.commit()
                flash(f"User '{username}' deleted successfully.", "success")
            else:
                flash(f"User '{username}' not found.", "error")
        except Exception as e:
            db.rollback()
            flash(f"Error deleting user: {str(e)}", "error")

        return redirect(url_for('admin'))  # Redirect back to admin page

    return render_template('delete_user.html')

@app.route('/temperature')
def temperature():
    if session.get('role') != 'temperature':
        return redirect(url_for('login'))

    data = get_sensor_data()  
    if data:
        latest = data[-1]['temperature']  # Get the 'temperature' from the last entry
    else:
        latest = None  

    alerts = []  
    if latest and latest > 30: 
        alerts.append("High temperature detected!")

    img = "data:image/png;base64," + generate_plot('temperature', 'Temperature (°C)', 'red')  # Create the plot
    
    return render_template('temperature.html', 
                           latest=latest, 
                           plot_url=img, 
                           alerts=alerts)

@app.route('/humidity')
def humidity():
    if session.get('role') != 'humidity':
        return redirect(url_for('login'))

    data = get_sensor_data()  # Get your sensor data
    if data:
        latest = data[-1]['humidity']  # Get the 'humidity' from the last entry
    else:
        latest = None 

    alerts = [] 
    if latest and latest > 80:
        alerts.append("High humidity detected!")

    img = "data:image/png;base64," + generate_plot('humidity', 'Humidity (%)', 'blue')  # Create the plot
    
    return render_template('humidity.html', 
                           latest=latest, 
                           plot_url=img, 
                           alerts=alerts)


@app.route('/ldr_inside') 
def ldr_inside():
    if session.get('role') != 'ldr_inside':
        return redirect(url_for('login'))

    data = get_sensor_data()

    latest_ldr = None
    latest_pir = None
    alerts = []

    if data:
        latest_entry = data[-1]

        # Safely extract keys using .get()
        latest_ldr = latest_entry.get('ldr1')
        latest_pir = latest_entry.get('pir')

        # Only alert if both conditions are met
        if latest_ldr is not None and latest_pir is not None:
            if latest_ldr < 100 and latest_pir == 1:
                alerts.append("Someone inside. Lights ON!")

    img = "data:image/png;base64," + generate_plot('ldr1', 'LDR Inside Reading', 'green')


    return render_template('ldr_inside.html', 
                           latest=latest_ldr, 
                           plot_url=img, 
                           alerts=alerts)



@app.route('/ldr_outside') 
def ldr_outside():
    if session.get('role') != 'ldr_outside':
        return redirect(url_for('login'))

    data = get_sensor_data()

    if data:
        latest = data[-1]
        latest_ldr = latest.get('ldr2')
        latest_pir = latest.get('pir')
    else:
        latest_ldr = None
        latest_pir = None

    alerts = []

    # Trigger alert only if LDR2 detects light and PIR detects no motion
    if latest_ldr is not None and latest_pir is not None:
        if latest_ldr > 100 and latest_pir == 0:
            alerts.append("Door open! No one is inside.")

    img = "data:image/png;base64," + generate_plot('ldr2', 'LDR Outside Reading', 'purple')
    
    return render_template('ldr_outside.html', 
                           latest_ldr=latest_ldr, 
                           latest_pir=latest_pir, 
                           plot_url=img, 
                           alerts=alerts)
@app.route('/pir')
def pir():
    if session.get('role') != 'pir':
        return redirect(url_for('login'))

    data = get_sensor_data() 
    if data:
        latest_pir = data[-1]['pir']  # Get the 'pir' from the last entry
    else:
        latest_pir = None

    alerts = [] 
    if latest_pir == 1: 
        alerts.append("Motion detected by PIR sensor!")
    img = "data:image/png;base64," + generate_pir_bar_plot()  # Create the plot
    
    return render_template('pir.html', 
                           latest_pir=latest_pir, 
                           plot_url=img, 
                           alerts=alerts)
@app.route('/cold_room', methods=['POST'])
def cold_room():
    if request.is_json:
        data = request.get_json()
        store_sensor_data(data)
        return {'status': 'success'}
    return {'status': 'fail'}, 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- Start the Flask Server ----------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
