import urllib.request
import json

def create_user(email, password, full_name, role):
    url = "http://localhost:8000/users/"
    data = json.dumps({
        "email": email,
        "password": password,
        "full_name": full_name,
        "role": role
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Created {email}: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"Failed to create {email}: {e.code} - {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error creating {email}: {e}")

if __name__ == "__main__":
    create_user("instructor@gradeops.io", "demo1234", "Demo Instructor", "teacher")
    create_user("ta@gradeops.io", "demo1234", "Demo TA", "student")
