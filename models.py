from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)

    props = db.relationship("Prop", backref="player", lazy=True)

class Prop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    stat_type = db.Column(db.String, nullable=False)  # e.g., "points"
    line = db.Column(db.Float, nullable=False)        # e.g., 25.5
    over_under = db.Column(db.String, nullable=False) # "over" or "under"


class Parlay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String)
    wager_amount = db.Column(db.Float)
    payout = db.Column(db.Float)
    result = db.Column(db.String)

    props = db.relationship('ParlayProp', backref='parlay', lazy=True)

class ParlayProp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parlay_id = db.Column(db.Integer, db.ForeignKey('parlay.id'), nullable=False)
    prop_id = db.Column(db.Integer, db.ForeignKey('prop.id'), nullable=False)

    prop = db.relationship("Prop", backref="parlay_links")

