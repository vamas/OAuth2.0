from flask import Flask, render_template, request, redirect,jsonify, url_for, flash
app = Flask(__name__)

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker

from database_setup import Base, Restaurant, MenuItem

#NEW Imports
from flask import session as login_session
import random, string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

from googlesignin import GoogleSignin, GoogleSigninError
from database_setup import Base, Restaurant, MenuItem, User
from localusermanager import LocalUserManager

#Connect to Database and create database session
engine = create_engine('sqlite:///restaurantmenuwithusers.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"

CLIENT_SECRETS = json.loads(open('client_secrets.json', 'r').read())



@app.route('/login')
def showLogin():
	state = ''.join(random.choice(string.ascii_uppercase + string.digits)
					for x in range(32))
	login_session['state'] = state
	return render_template('login.html', STATE=state)
	
@app.route('/gconnect', methods=['POST'])
def gconnect():
    try:
        googleSignin = GoogleSignin(auth_code=request.data, 
            state=login_session['state'],
            client_id=CLIENT_ID,
            client_secrets_filename='client_secrets.json',
            redirect_uri='postmessage',
            tokeninfo_url='https://www.googleapis.com/oauth2/v1/tokeninfo',
            userinfo_url='https://www.googleapis.com/oauth2/v1/userinfo',
            disconnect_url='')
        openUserSession(googleSignin.signin(request.args.get('state')))   
        LocalUserManager(session).createUserOrReturnExistingUser(login_session['username'],
            login_session['email'],
            login_session['picture'])
        return ''
    except GoogleSigninError as error:
        response = make_response(json.dumps(error.__dict__), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

@app.route('/gdisconnect')
def gdisconnect():
    if not isSigned():
        response = make_response(json.dumps('User is not signed in.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    try:
        googleSignin = GoogleSignin('','','','','','','','https://accounts.google.com/o/oauth2/revoke')
        googleSignin.signout(login_session['access_token'])
    except GoogleSigninError as error:
        response = make_response(json.dumps(error.__dict__), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    closeSigninSession()
    response = make_response(json.dumps('Successfully disconnected.'), 200)
    response.headers['Content-Type'] = 'application/json'
    return response

def isSigned():
    if login_session is None:
        return False
    if login_session.get('access_token', '') == '':
        print("Access token doesn't exist")
        return False
    return True

def openUserSession(signinStatus):
    login_session['access_token'] = signinStatus.access_token
    login_session['gplus_id'] = signinStatus.gplus_id
    login_session['username'] = signinStatus.username
    login_session['picture'] = signinStatus.picture
    login_session['email'] = signinStatus.email

def closeSigninSession():
    del login_session['access_token']
    del login_session['gplus_id']
    del login_session['username']
    del login_session['email']
    del login_session['picture']


#JSON APIs to view Restaurant Information
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])

@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id = menu_id).one()
    return jsonify(Menu_Item = Menu_Item.serialize)

@app.route('/restaurant/JSON')
def restaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(restaurants= [r.serialize for r in restaurants])


#Show all restaurants
@app.route('/')
@app.route('/restaurant/')
def showRestaurants():
    restaurants = session.query(Restaurant).order_by(asc(Restaurant.name))
    if isSigned():
        return render_template('restaurants.html', restaurants = restaurants)
    else:
        return render_template('publicrestaurants.html', restaurants = restaurants)

#Create a new restaurant
@app.route('/restaurant/new/', methods=['GET','POST'])
def newRestaurant():
    if not isSigned():
        return redirect('/login')
    if request.method == 'POST':
        dbSession = LocalUserManager(session)
        dbUserId = dbSession.getUserId(login_session['email'])
        newRestaurant = Restaurant(name = request.form['name'])
        newRestaurant.user_id = dbUserId
        session.add(newRestaurant)
        flash('New Restaurant %s Successfully Created' % newRestaurant.name)
        session.commit()
        return redirect(url_for('showRestaurants'))
    else:
        return render_template('newRestaurant.html')

#Edit a restaurant
@app.route('/restaurant/<int:restaurant_id>/edit/', methods = ['GET', 'POST'])
def editRestaurant(restaurant_id):
    if not isSigned():
        return redirect('/login')
    editedRestaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedRestaurant.name = request.form['name']
            flash('Restaurant Successfully Edited %s' % editedRestaurant.name)
            return redirect(url_for('showRestaurants'))
    else:
        return render_template('editRestaurant.html', restaurant = editedRestaurant)


#Delete a restaurant
@app.route('/restaurant/<int:restaurant_id>/delete/', methods = ['GET','POST'])
def deleteRestaurant(restaurant_id):
    if not isSigned():
        return redirect('/login')
    restaurantToDelete = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        session.delete(restaurantToDelete)
        flash('%s Successfully Deleted' % restaurantToDelete.name)
        session.commit()
        return redirect(url_for('showRestaurants', restaurant_id = restaurant_id))
    else:
        return render_template('deleteRestaurant.html',restaurant = restaurantToDelete)

#Show a restaurant menu
@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu/')
def showMenu(restaurant_id):    
    if not isSigned():
        return redirect('/login')
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
	
    dbSession = LocalUserManager(session)
    dbUserId = dbSession.getUserId(login_session['email'])
    if dbSession.isRestaurantUser(dbUserId, restaurant_id):   
        return render_template('menu.html', items = items, restaurant = restaurant)
    else:
        return render_template('publicmenu.html', items = items, 
            restaurant = restaurant, 
            creator = restaurant.user)
     
#Create a new menu item
@app.route('/restaurant/<int:restaurant_id>/menu/new/',methods=['GET','POST'])
def newMenuItem(restaurant_id):
    if not isSigned():
        return redirect('/login')
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        newItem = MenuItem(name = request.form['name'], description = request.form['description'], price = request.form['price'], course = request.form['course'], restaurant_id = restaurant_id)
        session.add(newItem)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newItem.name))
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('newmenuitem.html', restaurant_id = restaurant_id)

#Edit a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit', methods=['GET','POST'])
def editMenuItem(restaurant_id, menu_id):
    if not isSigned():
        return redirect('/login')
    editedItem = session.query(MenuItem).filter_by(id = menu_id).one()
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit() 
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('editmenuitem.html', restaurant_id = restaurant_id, menu_id = menu_id, item = editedItem)


#Delete a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete', methods = ['GET','POST'])
def deleteMenuItem(restaurant_id,menu_id):
    if not isSigned():
        return redirect('/login')
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    itemToDelete = session.query(MenuItem).filter_by(id = menu_id).one() 
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('deleteMenuItem.html', item = itemToDelete)

if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host = '0.0.0.0', port = 5000)
