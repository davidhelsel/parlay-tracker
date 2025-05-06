from flask import Flask, render_template, request, redirect
from models import db, Player, Prop, Parlay, ParlayProp
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parlays.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.route("/")
def home():
    parlays = Parlay.query.all()
    return render_template("list_parlays.html", parlays=parlays)

@app.route("/create_parlay", methods=["GET", "POST"])
def create_parlay():
    if request.method == "POST":
        date = request.form['date']
        wager = float(request.form['wager_amount'])
        payout = float(request.form['payout'])
        result = request.form['result']
        selected_prop_ids = request.form.getlist('props')  # List of prop IDs from checkboxes

        new_parlay = Parlay(date=date, wager_amount=wager, payout=payout, result=result)
        db.session.add(new_parlay)
        db.session.commit()

        for prop_id in selected_prop_ids:
            link = ParlayProp(parlay_id=new_parlay.id, prop_id=int(prop_id))
            db.session.add(link)

        db.session.commit()
        return redirect("/")

    props = Prop.query.all()
    players = Player.query.all()  # Make sure this line exists
    return render_template("create_parlay.html", props=props, players=players)

@app.route("/create_prop", methods=["GET", "POST"])
def create_prop():
    if request.method == "POST":
        player_id = int(request.form['player_id'])
        stat_type = request.form['stat_type']
        line = float(request.form['line'])
        over_under = request.form['over_under']

        new_prop = Prop(
            player_id=player_id,
            stat_type=stat_type,
            line=line,
            over_under=over_under
        )
        db.session.add(new_prop)
        db.session.commit()
        return redirect("/")

    players = Player.query.all()
    return render_template("create_prop.html", players=players)


@app.route("/create_player", methods=["GET", "POST"])
def create_player():
    if request.method == "POST":
        name = request.form['name']
        new_player = Player(name=name)
        db.session.add(new_player)
        db.session.commit()
        return redirect("/")

    return render_template("create_player.html")

@app.route("/select_parlay_to_update", methods=["GET", "POST"])
def select_parlay_to_update():
    if request.method == "POST":
        parlay_id = request.form['parlay_id']
        return redirect(f"/update_parlay/{parlay_id}")

    parlays = Parlay.query.all()
    return render_template("select_parlay_to_update.html", parlays=parlays)

@app.route("/update_parlay/<int:parlay_id>", methods=["GET", "POST"])
def update_parlay(parlay_id):
    parlay = Parlay.query.get_or_404(parlay_id)

    if request.method == "POST":
        # Update basic parlay info
        parlay.date = request.form['date']
        parlay.wager_amount = float(request.form['wager_amount'])
        parlay.payout = float(request.form['payout'])
        parlay.result = request.form['result']
        
        # Get selected prop IDs from form
        selected_prop_ids = request.form.getlist('props')
        
        # First, remove all existing prop links
        ParlayProp.query.filter_by(parlay_id=parlay.id).delete()
        
        # Then add the selected prop links
        for prop_id in selected_prop_ids:
            link = ParlayProp(parlay_id=parlay.id, prop_id=int(prop_id))
            db.session.add(link)
            
        db.session.commit()
        return redirect("/")

    # For GET request, get all props and players for the template
    props = Prop.query.all()
    players = Player.query.all()
    
    # Get the IDs of props that are currently in this parlay
    current_prop_ids = [link.prop_id for link in parlay.props]
    
    return render_template(
        "update_parlay.html", 
        parlay=parlay, 
        props=props, 
        players=players, 
        current_prop_ids=current_prop_ids
    )

@app.route("/delete_parlay/<int:parlay_id>", methods=["POST"])
def delete_parlay(parlay_id):
    parlay = Parlay.query.get_or_404(parlay_id)

    # First, delete links to props (ParlayProp entries)
    ParlayProp.query.filter_by(parlay_id=parlay.id).delete()

    # Then delete the parlay itself
    db.session.delete(parlay)
    db.session.commit()
    return redirect("/")

@app.route("/report_lebron_static")
def report_lebron_static():
    return render_template("report_lebron_static.html")

@app.route('/report')
def report():
    player_id = request.args.get('player_id', type=int)
    day = request.args.get('day')
    if player_id:
        # Use prepared statements for all queries
        # 1. Number of parlays involving this player
        num_parlays_sql = text("""
            SELECT COUNT(DISTINCT parlay.id) AS num_parlays
            FROM parlay
            JOIN parlay_prop ON parlay.id = parlay_prop.parlay_id
            JOIN prop ON parlay_prop.prop_id = prop.id
            WHERE prop.player_id = :player_id
        """)
        num_parlays = db.session.execute(num_parlays_sql, {'player_id': player_id}).scalar()

        # 2. Net earnings (sum of payouts for wins - sum of wagers for losses)
        net_earnings_sql = text("""
            SELECT
                COALESCE(SUM(CASE WHEN parlay.result = 'win' THEN parlay.payout ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN parlay.result = 'loss' THEN parlay.wager_amount ELSE 0 END), 0)
            FROM parlay
            JOIN parlay_prop ON parlay.id = parlay_prop.parlay_id
            JOIN prop ON parlay_prop.prop_id = prop.id
            WHERE prop.player_id = :player_id
        """)
        net_earnings = db.session.execute(net_earnings_sql, {'player_id': player_id}).scalar() or 0

        # 3. ROI = net_earnings / total wagered (on all parlays involving this player)
        total_wagered_sql = text("""
            SELECT COALESCE(SUM(parlay.wager_amount), 0)
            FROM parlay
            JOIN parlay_prop ON parlay.id = parlay_prop.parlay_id
            JOIN prop ON parlay_prop.prop_id = prop.id
            WHERE prop.player_id = :player_id
        """)
        total_wagered = db.session.execute(total_wagered_sql, {'player_id': player_id}).scalar() or 0

        roi = (net_earnings / total_wagered) if total_wagered > 0 else 0

        # 4. List of props for this player
        props_sql = text("""
            SELECT id, stat_type, line, over_under
            FROM prop
            WHERE player_id = :player_id
        """)
        props = db.session.execute(props_sql, {'player_id': player_id}).fetchall()

        # Get all parlays involving this player
        parlays_sql = text("""
            SELECT DISTINCT parlay.*
            FROM parlay
            JOIN parlay_prop ON parlay.id = parlay_prop.parlay_id
            JOIN prop ON parlay_prop.prop_id = prop.id
            WHERE prop.player_id = :player_id
            ORDER BY parlay.date DESC, parlay.id DESC
        """)
        parlays = db.session.execute(parlays_sql, {'player_id': player_id}).fetchall()

        player = Player.query.get_or_404(player_id)
        return render_template(
            'report_player_view.html',
            player=player,
            num_parlays=num_parlays,
            net_earnings=net_earnings,
            roi=roi,
            props=props,
            parlays=parlays  # Pass to template
        )
    if day:
        return redirect(f"/report/day/{day}")
    players = Player.query.all()
    dates = [row[0] for row in db.session.query(Parlay.date).distinct()]
    return render_template('report_selection.html',
                           players=players,
                           dates=dates)

@app.route('/report/day/<date>')
def report_day(date):
    # 1. Total wagered
    total_wagered_sql = text("""
        SELECT COALESCE(SUM(wager_amount), 0) FROM parlay WHERE date = :date
    """)
    total_wagered = db.session.execute(total_wagered_sql, {'date': date}).scalar() or 0

    # 2. Total won (sum of payout for winning parlays)
    total_won_sql = text("""
        SELECT COALESCE(SUM(payout), 0) FROM parlay WHERE date = :date AND result = 'win'
    """)
    total_won = db.session.execute(total_won_sql, {'date': date}).scalar() or 0

    # 3. Net earning
    net_earning = total_won - total_wagered

    # 4. Total parlays placed today
    total_parlays_sql = text("""
        SELECT COUNT(*) FROM parlay WHERE date = :date
    """)
    total_parlays = db.session.execute(total_parlays_sql, {'date': date}).scalar() or 0

    # 5. Percentage of parlays that were winners
    winning_parlays_sql = text("""
        SELECT COUNT(*) FROM parlay WHERE date = :date AND result = 'win'
    """)
    winning_parlays = db.session.execute(winning_parlays_sql, {'date': date}).scalar() or 0
    percent_winners = (winning_parlays / total_parlays * 100) if total_parlays > 0 else 0

    # 6. Best parlay (highest payout, only among winners)
    best_parlay_sql = text("""
        SELECT id, payout, wager_amount
        FROM parlay
        WHERE date = :date AND result = 'win'
        ORDER BY payout DESC
        LIMIT 1
    """)
    best_parlay = db.session.execute(best_parlay_sql, {'date': date}).fetchone()

    # 7. Highest earning player (most money won on parlays with that player)
    highest_player_sql = text("""
        SELECT player.id, player.name, 
               COALESCE(SUM(parlay.payout), 0) - COALESCE(SUM(parlay.wager_amount), 0) AS net_earning,
               COALESCE(SUM(parlay.payout), 0) AS total_won,
               COALESCE(SUM(parlay.wager_amount), 0) AS total_wagered
        FROM player
        JOIN prop ON prop.player_id = player.id
        JOIN parlay_prop ON prop.id = parlay_prop.prop_id
        JOIN parlay ON parlay_prop.parlay_id = parlay.id
        WHERE parlay.date = :date AND parlay.result = 'win'
        GROUP BY player.id
        ORDER BY net_earning DESC
        LIMIT 1
    """)
    highest_player = db.session.execute(highest_player_sql, {'date': date}).fetchone()

    # Get all parlays for this day
    parlays_sql = text("""
        SELECT * FROM parlay WHERE date = :date ORDER BY id DESC
    """)
    parlays = db.session.execute(parlays_sql, {'date': date}).fetchall()

    return render_template(
        "report_day_view.html",
        date=date,
        total_wagered=total_wagered,
        total_won=total_won,
        net_earning=net_earning,
        total_parlays=total_parlays,
        percent_winners=percent_winners,
        best_parlay=best_parlay,
        highest_player=highest_player,
        parlays=parlays  # Pass to template
    )

if __name__ == "__main__":
    app.run(debug=True)

