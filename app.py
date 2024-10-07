# Custom extension for IBM Watson Assistant which provides a
# REST API around a single database table (EVENTS).
#
# The code demonstrates how a simple REST API can be developed and
# then deployed as serverless app to IBM Cloud Code Engine.
#
# See the README and related tutorial for details.
#
# Written by Henrik Loeser (data-henrik), hloeser@de.ibm.com
# (C) 2022 by IBM

import os
import ast
from dotenv import load_dotenv
from apiflask import APIFlask, Schema, HTTPTokenAuth, PaginationSchema, pagination_builder, abort
from apiflask.fields import Integer, String, Boolean, Date, List, Nested
from apiflask.validators import Length, Range
# Database access using SQLAlchemy
from flask_sqlalchemy import SQLAlchemy

# Set how this API should be titled and the current version
API_TITLE='Events API for Watson Assistant'
API_VERSION='1.0.1'

# create the app
app = APIFlask(__name__, title=API_TITLE, version=API_VERSION)

# load .env if present
load_dotenv()

# the secret API key, plus we need a username in that record
API_TOKEN="{{'{0}':'appuser'}}".format(os.getenv('API_TOKEN'))
#convert to dict:
tokens=ast.literal_eval(API_TOKEN)

# database URI
DB2_URI=os.getenv('DB2triage_URI')
# optional table arguments, e.g., to set another table schema
ENV_TABLE_ARGS=os.getenv('TABLE_ARGS')
TABLE_ARGS=None
if ENV_TABLE_ARGS:
    TABLE_ARGS=ast.literal_eval(ENV_TABLE_ARGS)


# specify a generic SERVERS scheme for OpenAPI to allow both local testing
# and deployment on Code Engine with configuration within Watson Assistant
app.config['SERVERS'] = [
    {
        'description': 'Code Engine deployment',
        'url': 'https://{appname}.{projectid}.{region}.codeengine.appdomain.cloud',
        'variables':
        {
            "appname":
            {
                "default": "slackbottriage-backend",
                "description": "application name"
            },
            "projectid":
            {
                "default": "1mqn6ctvxequ",
                "description": "the Code Engine project ID"
            },
            "region":
            {
                "default": "us-south",
                "description": "the deployment region, e.g., us-south"
            }
        }
    },
    {
        'description': 'local test',
        'url': 'http://127.0.0.1:{port}',
        'variables':
        {
            'port':
            {
                'default': "5000",
                'description': 'local port to use'
            }
        }
    }
]


# set how we want the authentication API key to be passed
auth=HTTPTokenAuth(scheme='ApiKey', header='API_TOKEN')

# configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI']=DB2_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Initialize SQLAlchemy for our database
db = SQLAlchemy(app)


# sample records to be inserted after table recreation
sample_patients=[
    {
        "FNAME":"Patrick",
        "LNAME": "Dlamini",
        "IDENTITY":"0105232541085",
        "CELLNUM":"0609805147",
        "EMAIL": "johndoe@gmail.com",
        "GENDER":"Male",
        "HOMEADDRESS":"90 pain rd, durban",
        "PAINSCALE":"9",
        "PAINNATURE":"Pain in the abdomen",
        "IMMEDIATE":"true",
    },
    {
        "FNAME":"Patience",
        "LNAME": "Dlamini",
        "IDENTITY":"0105237771085",
        "CELLNUM":"0506587417",
        "EMAIL": "janedoe@gmail.com",
        "GENDER":"Female",
        "HOMEADDRESS":"10 injury rd, durban",
        "PAINSCALE":"2",
        "PAINNATURE":"Cough",
        "IMMEDIATE":"false",
    },

]


# Schema for table "EVENTS"
# Set default schema to "EVENTS"
class EventModel(db.Model):
    __tablename__ = 'PATIENTS'
    __table_args__ = TABLE_ARGS
    eid = db.Column('EID',db.Integer, primary_key=True)
    fname = db.Column('FNAME',db.String(32))
    lname = db.Column('LNAME',db.String(32))
    identity = db.Column('IDENTITY',db.String(13))
    cellnum = db.Column('CELLNUM',db.String(10))
    email = db.Column('EMAIL',db.String(32))
    gender = db.Column('GENDER',db.String(32))
    homeaddress = db.Column('HOMEADDRESS',db.String(32700))
    painscale = db.Column('PAINSCALE',db.Integer)
    painnature = db.Column('PAINNATURE',db.String(32))
    immediate = db.Column('IMMEDIATE',db.Boolean)

# the Python output for Events
class EventOutSchema(Schema):
    eid = Integer()
    fname = String()
    lname = String()
    identity = String()
    cellnum = String()
    email =String()
    gender = String()
    homeaddress = String()
    painscale = Integer()
    painnature = String()
    immediate = Boolean()

# the Python input for Events
class EventInSchema(Schema):
    fname = String(required=True)
    lname = String(required=True)
    identity = String(required=True, validate=Length(13))
    cellnum = String(required=True, validate=Length(10))
    email =String(required=True)
    gender = String(required=True)
    homeaddress = String(required=True)
    painscale = Integer(required=True)
    painnature = String(required=True)
    immediate = Boolean(required=True)

# use with pagination
class EventQuerySchema(Schema):
    page = Integer(load_default=1)
    per_page = Integer(load_default=20, validate=Range(max=30))

class EventsOutSchema(Schema):
    events = List(Nested(EventOutSchema))
    pagination = Nested(PaginationSchema)

# register a callback to verify the token
@auth.verify_token  
def verify_token(token):
    if token in tokens:
        return tokens[token]
    else:
        return None

# retrieve a single event record by EID
@app.get('/events/eid/<int:eid>')
@app.output(EventOutSchema)
@app.auth_required(auth)
def get_event_eid(eid):
    """Event record by EID
    Retrieve a single event record by its EID
    """
    return EventModel.query.get_or_404(eid)

# retrieve a single event record by name
@app.get('/patients/name/<string:fname>')
@app.output(EventOutSchema)
@app.auth_required(auth)
def get_event_name(fname):
    """Event record by name
    Retrieve a single event record by its short name
    """
    search="%{}%".format(fname)
    return EventModel.query.filter(EventModel.fname.like(search)).first()


# get all events
@app.get('/patients')
@app.input(EventQuerySchema, 'query')
#@app.input(EventInSchema(partial=True), location='query')
@app.output(EventsOutSchema)
@app.auth_required(auth)
def get_events(query):
    """all events
    Retrieve all event records
    """
    pagination = EventModel.query.paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    return {
        'patients': pagination.items,
        'pagination': pagination_builder(pagination)
    }

# create an event record
@app.post('/patients')
@app.input(EventInSchema, location='json')
@app.output(EventOutSchema, 201)
@app.auth_required(auth)
def create_event(data):
    """Insert a new event record
    Insert a new event record with the given attributes. Its new EID is returned.
    """
    event = EventModel(**data)
    db.session.add(event)
    db.session.commit()
    return event


# (re-)create the event table with sample records
@app.post('/database/recreate')
@app.input({'confirmation': Boolean(load_default=False)}, location='query')
#@app.output({}, 201)
@app.auth_required(auth)
def create_database(query):
    """Recreate the database schema
    Recreate the database schema and insert sample data.
    Request must be confirmed by passing query parameter.
    """
    if query['confirmation'] is True:
        db.drop_all()
        db.create_all()
        for e in sample_patients:
            event = EventModel(**e)
            db.session.add(event)
        db.session.commit()
    else:
        abort(400, message='confirmation is missing',
            detail={"error":"check the API for how to confirm"})
        return {"message": "error: confirmation is missing"}
    return {"message":"database recreated"}


# default "homepage", also needed for health check by Code Engine
@app.get('/')
def print_default():
    """ Greeting
    health check
    """
    # returning a dict equals to use jsonify()
    return {'message': 'This is the patients API server'}


# Start the actual app
# Get the PORT from environment or use the default
port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0',port=int(port))
