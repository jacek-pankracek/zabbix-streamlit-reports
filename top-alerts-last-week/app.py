# Requirements:
# pip install pip-system-certs pyzabbix pandas streamlit python-dotenv

import os
from dotenv import load_dotenv
from pyzabbix import ZabbixAPI
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import altair as alt
from streamlit_week_selector import streamlit_week_selector as week_selector

# Load .env file (optional)
load_dotenv()

# Read environment variables
ZABBIX_URL = os.getenv("ZABBIX_URL")
ZABBIX_TOKEN = os.getenv("ZABBIX_TOKEN")

# Connect using token
zapi = ZabbixAPI(ZABBIX_URL)
zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_TOKEN}"})
#zapi.login(token=ZABBIX_TOKEN)




# Default Time range
now = datetime.now()
start_time = int((now - timedelta(days=7)).timestamp())
end_time = int(now.timestamp())

def getEvents(start_time, end_time):

    # Fetch problem events
    events = zapi.event.get(
        time_from=start_time,
        time_till=end_time,
        value=1,
        selectHosts=["hostid", "name"],
        selectRelatedObject="extend",
        sortfield=["clock"],
        sortorder="DESC"
    )

    # Convert to DataFrame
    df = pd.DataFrame(events)
    df["clock"] = pd.to_datetime(df["clock"], unit="s")
    df["deviceid"] = df["hosts"].apply(lambda x: x[0]["hostid"] if x else None)
    df["devicename"] = df["hosts"].apply(lambda x: x[0]["name"] if x else None)
    df["itemid"] = df["relatedObject"].apply(lambda x: x.get("itemid") if x else None)

    df.rename(columns={"clock": "Date/Time", 
                        "devicename": "Host Name",
                        "deviceid": "Device ID",
                        "objectid": "Item ID",
                        "name": "Event Name"}, 
                        inplace=True)
    return df

st.set_page_config(page_title="Zabbix Problem Events Dashboard", 
                   layout="wide",
                   page_icon="./zabbix_icon.svg")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Choose a view:", ["All Events", "Summary Host-Item"])

if page == "All Events":


    # Week selector
    iso_week = week_selector()
    if iso_week is None:
        iso_week = datetime.now().strftime("%G-W%V")
    print(iso_week)

    # Get Monday of the ISO week
    start_date = datetime.strptime(iso_week + "-1", "%G-W%V-%u")
    end_date = start_date + timedelta(days=6)
    start_time = int(start_date.timestamp())
    end_time = int((end_date + timedelta(days=1)).timestamp())  # end is exclusive

    print("Start:", start_date, "→", start_time)
    print("End:", end_date, "→", start_time)

    st.title("Zabbix Problem Events (Last 7 Days)")
    df = getEvents(start_time, end_time)
    st.dataframe(df[["Date/Time", "Host Name", "Device ID", "Item ID", "Event Name"]], use_container_width=True)

# Page: Summary
elif page == "Summary Host-Item":
    st.title("Summary by DeviceID and ItemID")

    # Week selector
    iso_week = week_selector()
    if iso_week is None:
        iso_week = datetime.now().strftime("%G-W%V")
    print(iso_week)

    # Get Monday of the ISO week
    start_date = datetime.strptime(iso_week + "-1", "%G-W%V-%u")
    end_date = start_date + timedelta(days=6)
    start_time = int(start_date.timestamp())
    end_time = int((end_date + timedelta(days=1)).timestamp())  # end is exclusive

    df = getEvents(start_time, end_time)

    summary = df.groupby(["Host Name", "Event Name"]).size().reset_index(name="count")
    summary.sort_values(by="count", ascending=False, inplace=True)
    st.dataframe(summary)
    #st.bar_chart(summary.set_index("Host Name")["count"])

    chart = alt.Chart(summary).mark_bar().encode(
        x=alt.X("Host Name:N", sort="-y", title="Host Name"),
        y=alt.Y("count:Q", title="Event Count"),
        color="Event Name:N",
        tooltip=["Host Name", "Event Name", "count"]
    ).properties(
        width=800,
        height=400,
        title="Event Count by Host and Event Name"
    )

    st.altair_chart(chart, use_container_width=True)
