@app.route('/events')
def events():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    events = Event.query.order_by(Event.date).all()
    return render_template('events.html', events=events)