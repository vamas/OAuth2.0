from database_setup import User, Restaurant, MenuItem

class LocalUserManager(object):

    def __init__(self, dbsession):
        self.session = dbsession

    def createUser(self, username, email, picture):
        newUser = User(name=username, email=email, picture=picture)
        self.session.add(newUser)
        self.session.commit()
        user = self.session.query(User).filter_by(email=email).one()
        return user

    def createUserOrReturnExistingUser(self, username, email, picture):
        user_id = self.getUserId(email)
        if user_id == None:
            return self.createUser(username, email, picture)
        else:
            return self.getUserInfo(user_id)

    def getUserInfo(self, user_id):
        user = self.session.query(User).filter_by(id=user_id)
        return user

    def getUserId(self, email):
        try:
            user = self.session.query(User).filter_by(email=email).one()
            return user.id
        except:
            return None

    def getRestaurant(self, restaurant_id):
        try:
            restaurant = self.session.query(Restaurant).filter_by(id=restaurant_id).one()
            return restaurant
        except Exception as error:
            print(error)
            return None
    
    def isRestaurantUser(self, user_id, restaurant_id):
        restaurant = self.getRestaurant(restaurant_id)
        if restaurant is None:
            return False
        if restaurant.user_id == user_id:
            return True
        return False 




