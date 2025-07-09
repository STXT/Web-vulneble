from flask import Flask, request
import datetime

app = Flask(__name__)

@app.route("/xss")
def log_xss():
    value = request.args.get("value", "")
    with open("xss_verified.txt", "a") as f:
        f.write(f"{value}\n")
    return "OK"

if __name__ == "__main__":
    app.run(port=5000)
