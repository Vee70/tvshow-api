import json
import re
import requests
import sqlite3
import pandas as pd
from time import gmtime, strftime
from datetime import datetime, timedelta
from flask import Flask, request, send_file
from flask_restx import Api, Resource, fields, inputs, reqparse
import matplotlib.pyplot as plt


db_name = 'test.db'


def get_data(name):
    # fetch data from url
    r = requests.get('http://api.tvmaze.com/search/shows?q=' + name)
    if r.status_code == 200:
        data = r.json()
    else:
        print('{}, {}'.format(r.status_code, r.json()['message']))
        return None
    # format data
    title_sel = ''
    name = name.lower()
    final_data = None
    tmp_data = None
    # get exact match
    for i in range(len(data)):
        title = data[i]['show']['name'].lower()
        if re.search(rf'\b{name}\b', title):
            title_sel = title
            tmp_data = data[i]
            break
    # if exact match does not exist, get the closest match
    if tmp_data == None:
        for i in range(len(data)):
            title = data[i]['show']['name'].lower()
            if re.search(rf'{name}', title):
                title_sel = title
                tmp_data = data[i]
                break
    if title_sel != '':
        final_data = {
            'tvmaze_id': tmp_data['show']['id'],
            # 'id': tmp_data['show'][],
            'last_update': strftime("%Y-%m-%d-%H:%M:%S", gmtime()),
            'name': tmp_data['show']['name'],
            'type': tmp_data['show']['type'],
            'language': tmp_data['show']['language'],
            'genres': tmp_data['show']['genres'],
            'status': tmp_data['show']['status'],
            'runtime': tmp_data['show']['runtime'],
            'premiered': tmp_data['show']['premiered'],
            'officialSite': tmp_data['show']['officialSite'],
            'schedule': tmp_data['show']['schedule'],
            'rating': tmp_data['show']['rating'],
            'weight': tmp_data['show']['weight'],
            'network': tmp_data['show']['network'],
            'summary': tmp_data['show']['summary']
            # '_links': tmp_data['show']['_links']
        }
    return final_data

def create_table():
    con = sqlite3.connect(db_name)
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS tvshows (
        id INTEGER PRIMARY KEY,
        'tvmaze_id' INTEGER,
        'last_update' TEXT,
        name TEXT,
        type TEXT,
        language TEXT,
        genres TEXT,
        status TEXT,
        runtime INTEGER,
        premiered TEXT,
        officialSite TEXT,
        schedule TEXT,
        rating TEXT,
        weight INTEGER,
        network TEXT,
        summary TEXT
    )''')
    con.close()

def insert_data(data):
    con = sqlite3.connect(db_name)
    cur = con.cursor()
    cur.execute('''
        INSERT INTO tvshows (
            'tvmaze_id', 'last_update', name, type, language,
            genres, status, runtime, premiered, officialSite,
            schedule, rating, weight, network, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ''',
        (data['tvmaze_id'], data['last_update'], data['name'], data['type'],
        data['language'], str(data['genres']), data['status'], data['runtime'],
        data['premiered'], data['officialSite'], str(data['schedule']), str(data['rating']),
        data['weight'], str(data['network']), data['summary'])
    )
    con.commit()
    con.close()

def update_db(data):
    con = sqlite3.connect(db_name)
    cur = con.cursor()
    query = '''
        UPDATE tvshows
        SET
            'tvmaze_id' = ?, 'last_update' = ?, name = ?, type = ?, language = ?,
            genres = ?, status = ?, runtime = ?, premiered = ?, officialSite = ?,
            schedule = ?, rating = ?, weight = ?, network = ?, summary = ?
        WHERE
            id = ?
    '''
    cols = (
        data['tvmaze_id'], data['last_update'], data['name'], data['type'],
        data['language'], str(data['genres']), data['status'], data['runtime'],
        data['premiered'], data['officialSite'], str(data['schedule']), str(data['rating']),
        data['weight'], str(data['network']), data['summary'], data['id']
    )
    cur.execute(query, cols)
    con.commit()
    con.close()

# get self, previous and next tv show link
def get_links(self_id):
    # connect to databse
    con = sqlite3.connect(db_name)
    cur = con.cursor()
    url = request.host_url
    tmp = {}
    tmp['_links'] = {}
    tmp['_links']['self'] = {}
    tmp['_links']['self']['href'] = f'{url}tv-shows/{self_id}'
    # get link for previous tv show
    cur.execute(f'SELECT id FROM tvshows WHERE id < {self_id} ORDER BY id DESC LIMIT 1')
    v = cur.fetchall()
    if len(v) != 0:
        prev_id = v[0][0]
        tmp['_links']['previous'] = {}
        tmp['_links']['previous']['href'] = f'{url}tv-shows/{prev_id}'
    # get link for next tv show
    cur.execute(f'SELECT id FROM tvshows WHERE id > {self_id} ORDER BY id LIMIT 1')
    v = cur.fetchall()
    if len(v) != 0:
        next_id = v[0][0]
        tmp['_links']['next'] = {}
        tmp['_links']['next']['href'] = f'{url}tv-shows/{next_id}'
    con.close()
    return tmp


app = Flask(__name__)
api = Api(app)

# create schema for TV Show
schedual_model = api.model('schedule', {
    'time': fields.String,
    'days': fields.List(fields.String)
})

rating_model = api.model('rating', {
    'average': fields.Float
})

country_model = api.model('country', {
    'name': fields.String,
    'code': fields.String,
    'timezone': fields.String
})

network_model = api.model('network', {
    'id': fields.Integer,
    'name': fields.String,
    'country': fields.Nested(country_model)
})

tvshow_model = api.model('TVShow', {
    'id': fields.Integer,
    'tvmaze_id': fields.Integer,
    'last_update': fields.String,
    'name': fields.String,
    'type': fields.String,
    'language': fields.String,
    'genres': fields.List(fields.String),
    'status': fields.String,
    'runtime': fields.Integer,
    'premiered': fields.String,
    'officialSite': fields.String,
    'schedule': fields.Nested(schedual_model),
    'rating': fields.Nested(rating_model),
    'weight': fields.Integer,
    'network': fields.Nested(network_model),
    'summary': fields.String,
})

parser = reqparse.RequestParser()
parser.add_argument('order', choices=list(col for col in tvshow_model.keys()))
parser.add_argument('ascending', type=inputs.boolean)


@api.route('/tv-shows')
class TVShowList(Resource):

    @api.response(201, 'TV Show imported successfully')
    @api.response(400, 'Validation Error')
    @api.response(404, 'TV Show not found')
    @api.doc(description='Add a new TV Show')
    @api.expect(reqparse.RequestParser().add_argument('name',  type='str', help='TV Show name', required=True))
    def post(self):
        # connect to database
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        # get input name
        parser = reqparse.RequestParser()
        parser.add_argument('name')
        args = parser.parse_args()
        name = args.get('name')
        # get data from ' http://api.tvmaze.com/search/shows?q=<name>'
        data = get_data(name)
        # check if tv show exist
        if data == None:
            api.abort(404, 'TV Show: {} does not exist'.format(name))
        tvmaze_id = data['tvmaze_id']
        cur.execute(f'SELECT * FROM tvshows WHERE "tvmaze_id"={tvmaze_id}')
        if len(cur.fetchall()) != 0:
            api.abort(400, 'TV Show with tvmaze_id={} is already in the database'.format(tvmaze_id))
        # store data in database
        insert_data(data)
        # retrieve data
        tvmaze_id = data['tvmaze_id']
        cur.execute(f'SELECT * FROM tvshows WHERE "tvmaze_id"={tvmaze_id}')
        data = list(cur.fetchall()[0])
        # close connection
        con.close()
        return {
            'id': data[0],
            'last-update': data[2],
            'tvmaze-id': data[1],
            '_links': get_links(data[0])['_links']
        }

    @api.response(200, 'Successful')
    @api.response(404, 'TV Show does not exist')
    @api.expect(reqparse.RequestParser().add_argument(
        'page', type=int,
    ).add_argument(
        'page_size', type=int
    ).add_argument(
        'order_by', type='str', 
        help='+id, -id, +rating-average, -rating-average, +premiered, -premiered'
    ).add_argument(
        'filter', type='str',
        help='tvmaze_id, id, last_update, name, type, language, genres, status, runtime, premiered, officialSite, schedule, rating, weight, network, summary'
    ))
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('page')
        parser.add_argument('page_size')
        parser.add_argument('order_by')
        parser.add_argument('filter')
        args = parser.parse_args()
        # get input
        page = args.get('page')
        page_size = args.get('page_size')
        order = args.get('order_by')
        flter = args.get('filter')
        orders_by = {
            '+id': 'id ASC',
            '-id': 'id DESC',
            '+rating-average': 'rating ASC',
            '-rating-average': 'rating DESC',
            '+premiered': 'premiered ASC',
            '-premiered': 'premiered DESC'
        }
        # get all inputs values
        if page is None:
            page = 1
        else:
            page = int(page)
            if page == 0:
                api.abort(404, 'Page 0 does not exist')
        if page_size is None:
            page_size = 100
        else:
            page_size = int(page_size)
        if order is None:
            order = 'id ASC'
        else:
            # check if input is valid
            temp = order.strip().replace(' ', '').split(',')
            if not set(temp).issubset(set(orders_by.keys())):
                api.abort(404, 'Invalid input')
            for key, val in orders_by.items():
                order = order.replace(key, val)
        if flter is None:
            flter = 'id, name'
        cols = flter.strip().replace(' ', '').split(',')
        # check if input is valid
        tmp = [
            'tvmaze_id', 'id', 'last_update', 'name', 'type', 'language', 
            'genres', 'status', 'runtime', 'premiered', 'officialSite', 
            'schedule', 'rating', 'weight', 'network', 'summary'
        ]
        if not set(cols).issubset(set(tmp)):
            api.abort(404, 'Invalid input')
        # connect to database
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        # get data from db
        cur.execute(f'SELECT {flter} FROM tvshows ORDER BY {order}')
        data = list(cur.fetchall())
        # format data
        tv_shows = []
        for d in data:
            tv_shows.append({cols[i]: d[i] for i in range(len(d))})
        for i in range(len(tv_shows)):
            for key in tv_shows[i].keys():
                if key in ['genres', 'schedule', 'rating', 'network']:
                    tv_shows[i][key] = eval(tv_shows[i][key])
        output = {}
        url = request.host_url
        for i in range(int(page)):
            output[i+1] = {}
            output[i+1]['page'] = i+1
            output[i+1]['page-size'] = page_size
            output[i+1]['tv-shows'] = tv_shows[i*page_size:(i+1)*page_size]
            # get links
            for key, val in orders_by.items():
                order = order.replace(val, key)
            od = order.strip().replace(r' ', '')
            f = flter.strip().replace(r' ', '')
            output[i+1]['_links'] = {}
            output[i+1]['_links']['self'] = {
                'href': f'{url}tv-shows?order_by={od}&page={i+1}&page_size={page_size}&filter={f}'
            }
            if i > 0:
                output[i+1]['_links']['previous'] = {
                    'href': f'{url}tv-shows?order_by={od}&page={i}&page_size={page_size}&filter={f}'
                }
            output[i+1]['_links']['next'] = {
                'href': f'{url}tv-shows?order_by={od}&page={i+2}&page_size={page_size}&filter={f}'
            }
        return output[page]


@api.route('/tv-shows/<int:id>')
@api.param('id', 'TV Show ID')
class TVShow(Resource):

    @api.response(200, 'successful')
    @api.response(404, 'TV show not found')
    @api.doc(description='Get TV show by ID')
    def get(self, id):
        # connect to database
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        # check if tv show exist
        cur.execute(f'SELECT * FROM tvshows WHERE id={id}')
        if len(cur.fetchall()) == 0:
            api.abort(404, 'TV Show with id={} does not exist'.format(id))
        # retrieve data
        cur.execute(f'SELECT * FROM tvshows WHERE id={id}')
        data = list(cur.fetchall()[0])
        # close connection
        con.close()
        return {
            'tvmaze_id': data[1],
            'id': data[0],
            'last_update': data[2],
            'name': data[3],
            'type': data[4],
            'language': data[5],
            'genres': eval(data[6]),
            'status': data[7],
            'runtime': data[8],
            'premiered': data[9],
            'officialSite': data[10],
            'schedule': eval(data[11]),
            'rating': eval(data[12]),
            'weight': data[13],
            'network': eval(data[14]),
            'summary': data[15],
            '_links': get_links(data[0])['_links']
        }

    @api.response(200, 'Successful')
    @api.response(404, 'TV show not found')
    @api.doc(description='Delete a TV show by ID')
    def delete(self, id):
        # connect to database
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        # check if tv show exist
        cur.execute(f'SELECT * FROM tvshows WHERE id={id}')
        if len(cur.fetchall()) == 0:
            api.abort(404, 'TV Show with id={} does not exist'.format(id))
        # delete row from database
        cur.execute(f'DELETE FROM tvshows WHERE id={id}')
        con.commit()
        con.close()
        return {
            'message': 'The tv show with id {} was removed from the database!'.format(id),
            'id': id
        }, 200

    @api.response(200, 'Successful')
    @api.response(400, 'Validation Error')
    @api.response(404, 'TV show not found')
    @api.expect(tvshow_model, validate=True)
    @api.doc(description="Update a TV show by ID")
    def patch(self, id):
        # connect to database
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        # check if tv show exist
        cur.execute(f'SELECT * FROM tvshows WHERE id={id}')
        if len(cur.fetchall()) == 0:
            api.abort(404, 'TV Show with id={} does not exist'.format(id))
        # get payload and convert it to JSON
        tvshow = request.json
        # retrieve data
        cur.execute(f'SELECT * FROM tvshows WHERE id={id}')
        data = list(cur.fetchall()[0])
        data = {
            'tvmaze_id': data[1], 'id': data[0], 'last_update': data[2], 'name': data[3],
            'type': data[4], 'language': data[5], 'genres': eval(data[6]), 'status': data[7],
            'runtime': data[8], 'premiered': data[9], 'officialSite': data[10],
            'schedule': eval(data[11]), 'rating': eval(data[12]), 'weight': data[13],
            'network': eval(data[14]), 'summary': data[15]
        }
        # make sure that TV show id and tvmaze_id cannot be changed
        if 'id' in data and id != tvshow['id']:
            return {'message': 'id cannot be changed'.format(id)}, 400
        # update the values
        # only update the value that user edit
        last_update = ''
        for key in tvshow.keys():
            if key not in tvshow_model.keys():
                return {'message': 'Property {} is invalid'.format(key)}, 400
            if key == 'id' or key == 'tvmaze_id' or key == 'last_update': continue
            if key == 'genres':
                if tvshow[key][0] == 'string': continue
            if key == 'rating':
                if tvshow[key]['average'] == 0: continue
            if tvshow[key] == 'string' or tvshow[key] == 0: continue
            if key == 'schedule':
                if tvshow[key]['time'] != 'string':
                    data[key]['time'] = tvshow[key]['time']
                if tvshow[key]['days'][0] != 'string':
                    data[key]['days'] = tvshow[key]['days']
                continue
            if key == 'network':
                if tvshow[key]['id'] != 0:
                    data[key]['id'] = tvshow[key]['id']
                if tvshow[key]['name'] != 'string':
                    data[key]['name'] = tvshow[key]['string']
                if tvshow[key]['country']['name'] != 'string':
                    data[key]['country']['name'] = tvshow[key]['country']['name']
                if tvshow[key]['country']['code'] != 'string':
                    data[key]['country']['code'] = tvshow[key]['country']['code']
                if tvshow[key]['country']['timezone'] != 'string':
                    data[key]['country']['timezone'] = tvshow[key]['country']['timezone']
                continue
            if tvshow[key] == 0 or tvshow[key] == 'string': continue
            last_update = str(strftime("%Y-%m-%d-%H:%M:%S", gmtime()))
            data[key] = tvshow[key]
        # if no change is made, return
        if last_update == '':
            con.close()
            return {'message': 'No value has changed'}
        # update the database
        data['last_update'] = last_update
        update_db(data)
        # close connection
        con.close()
        return {
            'id': id,
            'last-update': last_update,
            '_links': get_links(id)['_links']
        }


@api.route('/tv-shows/statistics')
class TVShowStatistics(Resource):

    @api.response(200, 'Successful')
    @api.response(404, 'TV Show does not exist')
    @api.expect(reqparse.RequestParser().add_argument(
        'format', type='str', 
        help='json, image'
    ).add_argument(
        'by', type='str',
        help='language, genres, status, type'
    ))
    def get(self):
        # get input
        parser = reqparse.RequestParser()
        parser.add_argument('format')
        parser.add_argument('by')
        args = parser.parse_args()
        format = args.get('format')
        by = args.get('by')
        by = by.strip().replace(r' ', '')
        # check if input is valid
        if format not in ['json', 'image']: 
            api.abort(404, 'Invalid input')
        if by not in ['language', 'genres', 'status', 'type']:
            api.abort(404, 'Invalid input')
        # connect to database
        con = sqlite3.connect(db_name)
        cur = con.cursor()
        # get total number of tv shows in db
        cur.execute(f'SELECT COUNT(id) FROM tvshows')
        total = cur.fetchall()[0][0]
        # get total updated in the last 24h
        cur.execute(f"SELECT COUNT(id) FROM tvshows WHERE last_update >= datetime('now','-86400 second') AND last_update <= strftime('%Y-%m-%d-%H:%M:%S', 'now')")
        total_update = cur.fetchall()[0][0]
        # if language in input, get percentage of languages
        value = None
        if by == 'language':
            cur.execute(f'SELECT language FROM tvshows')
            languages = list(cur.fetchall())
            languages_count = {}
            total_languages_count = 0
            for i in languages:
                for lang in i:
                    if lang == None:
                        lang = 'Unknown'
                    if lang not in languages_count.keys():
                        languages_count[lang] = 1
                        total_languages_count += 1
                    else:
                        languages_count[lang] += 1
                        total_languages_count += 1
            # get percentage
            for lang, count in languages_count.items():
                languages_count[lang] = round((count/total_languages_count)*100, 1)
            value = languages_count
            title = 'Language'
        # if genres in input, get percentage of genres
        elif by == 'genres':
            cur.execute(f'SELECT genres FROM tvshows')
            genres = list(cur.fetchall())
            genres_count = {}
            total_genres_count = 0
            for i in genres:
                for gen in i:
                    for g in eval(gen):
                        if g == None:
                            g = 'Unknown'
                        if g not in genres_count.keys():
                            genres_count[g] = 1
                            total_genres_count += 1
                        else:
                            genres_count[g] += 1
                            total_genres_count += 1
            # get percentage
            for g, count in genres_count.items():
                genres_count[g] = round((count/total_genres_count)*100, 1)
            value = genres_count
            title = 'Genres'
        elif by == 'status':
            cur.execute(f'SELECT status FROM tvshows')
            status = list(cur.fetchall())
            status_count = {}
            total_status_count = 0
            for i in status:
                for st in i:
                    if st == None:
                        st = 'Unknown'
                    if st not in status_count.keys():
                        status_count[st] = 1
                        total_status_count += 1
                    else:
                        status_count[st] += 1
                        total_status_count += 1
            # get percentage
            for st, count in status_count.items():
                status_count[st] = round((count/total_status_count)*100, 1)
            value = status_count
            title = 'Status'
        # if input is type
        elif by == 'type':
            cur.execute(f'SELECT type FROM tvshows')
            types = list(cur.fetchall())
            types_count = {}
            total_types_count = 0
            for i in types:
                for t in i:
                    if t == None:
                        t = 'Unknown'
                    if t not in types_count.keys():
                        types_count[t] = 1
                        total_types_count += 1
                    else:
                        types_count[t] += 1
                        total_types_count += 1
            # get percentage
            for t, count in types_count.items():
                types_count[t] = round((count/total_types_count)*100, 1)
            value = types_count
            title = 'Type'
        if format == 'json':
            return {
                'total': total,
                'total_update': total_update,
                'values': value
            }
        data =  {
            'total': total,
            'total_update': total_update,
            'values': value
        }
        df = pd.DataFrame.from_dict(data)
        fig, axs = plt.subplots(2, 1, figsize=(10, 20))
        patches, texts, autotexts = axs[0].pie(df.iloc[:, -1], labels=df.index, autopct='%1.1f%%')
        for i in range(len(texts)):
            texts[i].set_fontsize(10)
            autotexts[i].set_fontsize(8)
        axs[0].set_title(title, size=15)
        patches, texts = axs[1].bar(['Total TV Shows', 'Total-updated TV Shows in the last 24h'], [total, total_update], width=0.3)
        axs[1].set_title('Total TV Shows and total updated TV Shows in the last 24h', size=15)
        plt.setp(axs[1].get_xticklabels(), fontsize=10)
        plt.setp(axs[1].get_yticklabels(), fontsize=10)
        fig.savefig('out.png')
        return send_file(
            'out.png',
            cache_timeout=-1
        )


if __name__ == '__main__':

    # db_name = 'test.db'
    con = sqlite3.connect(db_name)
    create_table()
    con.close()

    app.run(debug=True)
