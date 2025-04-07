from datetime import datetime

def init_filters(app):
    @app.template_filter('format_last_seen')
    def format_last_seen(value):
        if not value:
            return 'Never'
        now = datetime.now()
        diff = now - value
        if diff.total_seconds() < 60:
            return 'Just now'
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes} minutes ago'
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f'{hours} hours ago'
        else:
            days = int(diff.total_seconds() / 86400)
            return f'{days} days ago'  

    @app.template_filter('format_date')
    def format_date(value):
        return value.strftime('%d %b %Y')
    
    @app.template_filter('format_time')
    def format_time(value):
        return value.strftime('%H:%M:%S')
    
    @app.template_filter('format_datetime')
    def format_datetime(value):
        # 15 Jan 2021 07:00 PM
        return value.strftime('%d %b %Y %I:%M %p')