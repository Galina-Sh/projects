from __future__ import print_function
import os
import logging
from slack_sdk import WebClient
import re
import psycopg2
import pandas as pd
import gspread
import datetime as dt
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from tabulate import tabulate


# SLACK APP:

client = WebClient(token=os.environ['MA_SLACK_BOT_TOKEN'])  # test-bot Bot User OAuth Token
logger = logging.getLogger(__name__)
channel_id_to_write = 'C01UJ14PN58'  # 'C02L1262NKZ' test-bot 3,  'C01UJ14PN58' production_ma


app = App(token=os.environ['MA_SLACK_BOT_TOKEN'],
          signing_secret=os.environ['MA_SLACK_SIGNING_SECRET'])


@app.event("app_mention")
def handle_event(body, payload, context, logger):
    text = payload.get('text')
    tail = parsing_aircraft(text)
    pricelist = parsing_locations(text)
    mtow = int(float(get_info_for_tail(tail).split()[0]))
    designator = get_info_for_tail(tail).split()[1]
    today = dt.datetime.today()
    business_days = 6
    date_of_release = date_by_adding_business_days(today, business_days).strftime('%#d %b %Y')
    get_table_pipeline(pricelist)
    get_table_requests(designator, pricelist)
    df_merge_1 = get_table_pipeline(pricelist).merge(get_table_requests(designator, pricelist), left_on='Pricelist',
                                                     right_on='Pricelist')
    df_merge_2 = df_merge_1.merge(get_table_ma_responsible(pricelist), how='right')
    df_final = tabulate(df_merge_2, headers='keys', showindex=False, tablefmt='psql')
    print(payload.get('channel'), payload.get('ts'))
    print(df_final)

    try:
        client.chat_postMessage(
            # mrkdwn=True,
            channel=channel_id_to_write,
            text='<!subteam^S025WMD2KL6|@ma>' + '\n' + 'Tail number: ' + parsing_aircraft(
                text) + '\n' + 'Date of release: ' + date_of_release + '\n' + 'Aircaft, MTOW(kg) : ' + designator + ', ' + str(mtow) + '\n' +
                 'Extended list:' + '\n' + '```' + df_final + '```')

        client.reactions_add(
            channel=payload.get('channel'),
            name='heavy_check_mark',
            timestamp=payload.get('ts'))

    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

    pass


@app.event("message")
def handle_message_events():
    pass


# Step 1: parsing Slack message

def parsing_aircraft(text):
    search_aircraft = re.search(r'AC:(\w+)', text)
    tail_number = search_aircraft.group(1)  # <re.Match object; span=(0, 9), match='AC:N313ZP'>
    return tail_number


def parsing_locations(text):
    text = text.replace(' ', '')
    search_location = re.search(r'.*AP:([\w,]*).*', text, re.M | re.I)
    locations = search_location.group(1)
    list_of_locations = [loc for loc in locations.split(',')]
    return list_of_locations


# Step 2: SQL request

def select(sql):
    conn = None
    try:
        conn = psycopg2.connect(host=os.environ['HOSTNAME'], dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'])
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchall()
    except Exception as exc:
        if conn:
            conn.rollback()
            print('con_error:' + str(exc))
        raise exc
    finally:
        conn.close()


def get_info_for_tail(tail):
    data_set_from_sql = select(
        """SELECT aircrafts.tail_number,aircraft_techspecs.max_takeoff_weight,aircraft_models.type_designator FROM 
        aircrafts LEFT JOIN aircraft_techspecs ON aircraft_techspecs.aircraft_id=aircrafts.id LEFT JOIN 
        aircraft_models ON aircraft_models.id=aircrafts.aircraft_model_id where tail_number = '{}';""".format(tail))

    res = pd.DataFrame(data_set_from_sql, columns=['tail_number', 'max_takeoff_weight', 'type_designator'])
    result_to_print = res[['max_takeoff_weight', 'type_designator']]

    if result_to_print.empty:
        return None

    return result_to_print.to_string(index=False, header=False)


# Step 4: Date of release calculation

def date_by_adding_business_days(today, business_days):
    business_days_to_add = business_days
    current_date = today
    while business_days_to_add > 0:
        current_date += dt.timedelta(days=1)
        weekday = current_date.weekday()
        if weekday >= 5:
            continue
        business_days_to_add -= 1
    return current_date


# Step 5: Pipeline search

pd.options.mode.chained_assignment = None  # чтобы убрать ошибку SettingWithCopyWarning: A value is trying to be set on a copy of a slice from a DataFrame


def get_table_pipeline(pricelist):
    gs = gspread.service_account_from_dict({
        "type": os.environ['TYPE'],
        "project_id": os.environ['PROJECT_ID'],
        "private_key_id": os.environ['PRLIST_PRIVATE_KEY_ID'],
        "private_key": os.environ['PRLIST_PRIVATE_KEY'].replace('\\n', '\n'),
        "client_email": os.environ['PRLIST_CLIENT_EMAIL'],
        "client_id": os.environ['PRLIST_CLIENT_ID'],
        "auth_uri": os.environ['AUTH_URI'],
        "token_uri": os.environ['TOKEN_URI'],
        "auth_provider_x509_cert_url": os.environ['AUTH_PROVIDER'],
        "client_x509_cert_url": os.environ['PRLIST_CLIENT_URL']
    })
    sheet = gs.open_by_key(os.environ['PIPELINE_SPREADSHEET_ID'])
    worksheet = sheet.sheet1
    result = worksheet.get_all_values()
    dataframe = pd.DataFrame(result).drop(labels=None, axis=0, index=[0, 1])
    dataframe = dataframe.loc[:, [1, 4]]  # dataframe with all pipeline locations
    df_pipeline = dataframe.loc[dataframe[1].isin(pricelist)]  # dataframe with all requested locations
    df_pipeline.loc[df_pipeline[4] == 'In Request', 4] = 'Need to request'
    df_pipeline.loc[df_pipeline[4] == 'Checked', 4] = 'Received'
    df_pipeline.loc[df_pipeline[4] == 'Not Started', 4] = 'Received'
    df_pipeline.columns = ['Pricelist', 'Status']
    df_pipeline = df_pipeline.reset_index(drop=True)
    df_pricelists = pd.DataFrame(pricelist)
    df_pricelists.columns = ['Pricelist']
    df_common = df_pricelists.merge(df_pipeline, how='left')
    df_common = df_common.fillna('Check Pipeline')
    return df_common


# Step 6: Requests (MA) search


def get_table_requests(designator, pricelist):
    gs = gspread.service_account_from_dict({
        "type": os.environ['TYPE'],
        "project_id": os.environ['PROJECT_ID'],
        "private_key_id": os.environ['PRLIST_PRIVATE_KEY_ID'],
        "private_key": os.environ['PRLIST_PRIVATE_KEY'].replace('\\n', '\n'),
        "client_email": os.environ['PRLIST_CLIENT_EMAIL'],
        "client_id": os.environ['PRLIST_CLIENT_ID'],
        "auth_uri": os.environ['AUTH_URI'],
        "token_uri": os.environ['TOKEN_URI'],
        "auth_provider_x509_cert_url": os.environ['AUTH_PROVIDER'],
        "client_x509_cert_url": os.environ['PRLIST_CLIENT_URL']
    })
    sheet = gs.open_by_key(os.environ['REQUESTS_SPREADSHEET_ID'])
    worksheet = sheet.sheet1
    result = worksheet.get_all_values()
    dataframe = pd.DataFrame(result)
    list_of_headers = dataframe.loc[1].values.tolist()
    dataframe.columns = list_of_headers
    dataframe = dataframe.rename(columns={'ICAO': 'Pricelist'})
    dataframe = dataframe.drop(labels=None, axis=0, index=[0, 1, 2])
    dataframe = dataframe.drop(['Responsibility'], axis=1)
    dataframe = dataframe.reset_index(drop=True)
    df_requests = dataframe.loc[:, ['Pricelist', designator]]
    df_requests.loc[df_requests[designator] == 'done', designator] = 'received'
    df_requests.loc[df_requests[designator] == 'part', designator] = 'received'
    df_requests.loc[df_requests[designator] == '1', designator] = 'Need to request'
    df_requests.loc[df_requests[designator] == '2', designator] = 'Need to request'
    df_requests.loc[df_requests[designator] == '', designator] = 'Need to request'
    df_pricelists = pd.DataFrame(pricelist)
    df_pricelists.columns = ['Pricelist']
    df_common = df_pricelists.merge(df_requests, how='left')
    df_common = df_common.fillna('Need to request')
    return df_common


# Step 7: MA responsible search

# ma_responsible = {'Tatiana Kartushova': 'U21B6HJBV', 'Anastasiya Selezneva': 'U02BKTR0P5J', 'Maggie Shablevskaya': 'U02RBQ1PH51', 'Gornostaev Viacheslav': 'U01RATGLN22'}

def get_table_ma_responsible(pricelist):
    gs = gspread.service_account_from_dict({
        "type": os.environ['TYPE'],
        "project_id": os.environ['PROJECT_ID'],
        "private_key_id": os.environ['PRLIST_PRIVATE_KEY_ID'],
        "private_key": os.environ['PRLIST_PRIVATE_KEY'].replace('\\n', '\n'),
        "client_email": os.environ['PRLIST_CLIENT_EMAIL'],
        "client_id": os.environ['PRLIST_CLIENT_ID'],
        "auth_uri": os.environ['AUTH_URI'],
        "token_uri": os.environ['TOKEN_URI'],
        "auth_provider_x509_cert_url": os.environ['AUTH_PROVIDER'],
        "client_x509_cert_url": os.environ['PRLIST_CLIENT_URL']
    })
    sheet = gs.open_by_key(os.environ['MA_RESPONSIBLE_SPREADSHEET_ID'])
    worksheet = sheet.sheet1
    result = worksheet.get_all_values()
    dataframe = pd.DataFrame(result).drop(labels=None, axis=0, index=[0, 1])
    dataframe = dataframe.loc[:, [1, 2]]

    list_of_responsible = [None] * len(pricelist)
    for i in range(len(pricelist)):
        for j in range(len(dataframe.index)):
            if pricelist[i] == dataframe.iloc[j, 0] or pricelist[i][:3] == dataframe.iloc[j, 0] or \
                    pricelist[i][:2] == dataframe.iloc[j, 0] or pricelist[i][1] == dataframe.iloc[j, 0]:
                list_of_responsible[i] = dataframe.iloc[j, 1]
        if list_of_responsible[i] is None:
            list_of_responsible[i] = 'Tatiana Kartushova'
    data = [pricelist, list_of_responsible]
    dfresponsible = pd.DataFrame(data).T
    dfresponsible.columns=['Pricelist', 'Responsible']
    return dfresponsible


if __name__ == "__main__":
    SocketModeHandler(app, os.environ['MA_SLACK_APP_TOKEN']).start()