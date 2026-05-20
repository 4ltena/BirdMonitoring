from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, pytz

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "postgresql://bird:bird@localhost/bird_monitor"
)
db = SQLAlchemy(app)
JST = pytz.timezone("Asia/Tokyo")

class SensorLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    temp       = db.Column(db.Float)
    hum        = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(JST))

class CageStatus(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    mode          = db.Column(db.String(20))
    bird_detected = db.Column(db.Integer)
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(JST))

@app.route("/")
def index():
    latest_log    = SensorLog.query.order_by(SensorLog.created_at.desc()).first()
    latest_status = CageStatus.query.order_by(CageStatus.updated_at.desc()).first()
    return render_template("index.html", log=latest_log, status=latest_status)

@app.route("/api/health", methods=["POST"])
def receive_health():
    data = request.get_json()
    mode = data.get("mode", "")
    detected = int(data.get("bird_detected", False))
    db.session.add(CageStatus(mode=mode, bird_detected=detected))
    if data.get("temperature") is not None:
        db.session.add(SensorLog(temp=data["temperature"], hum=data["humidity"]))
    db.session.commit()
    return {"result": "ok"}, 201

@app.route("/api/status", methods=["GET"])
def get_status():
    latest = CageStatus.query.order_by(CageStatus.updated_at.desc()).first()
    outside = (latest.mode == "OUTSIDE") if latest else False
    return jsonify({
        "bird_outside": outside,
        "mode": latest.mode if latest else "unknown",
        "bird_detected": bool(latest.bird_detected) if latest else False
    })

@app.route("/api/sensor_data_list", methods=["GET"])
def sensor_data_list():
    logs = SensorLog.query.order_by(SensorLog.created_at.asc()).all()
    return jsonify([{
        "temp": l.temp, "hum": l.hum,
        "time": l.created_at.strftime("%H:%M:%S")
    } for l in logs])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=False)
