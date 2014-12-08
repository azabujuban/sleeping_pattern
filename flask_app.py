
# A very simple Flask Hello World app for you to get started with...

from flask import Flask

from play import main

app = Flask(__name__, static_url_path='/home/maxint/sleeping')

@app.route('/')
def hello_world():
    main()
    return app.send_static_file('sleeping.html')
