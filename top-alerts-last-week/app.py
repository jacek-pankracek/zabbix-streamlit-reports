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
    events = zapi.event.get(
        time_from=start_time,
        time_till=end_time,
        value=1,
        selectHosts=["hostid", "name"],
        selectRelatedObject="extend",
        sortfield=["clock"],
        sortorder="DESC"
    )

    df = pd.DataFrame(events)
    df["clock"] = pd.to_datetime(df["clock"], unit="s")
    df["deviceid"] = df["hosts"].apply(lambda x: x[0]["hostid"] if x else None)
    df["devicename"] = df["hosts"].apply(lambda x: x[0]["name"] if x else None)
    df["itemid"] = df["relatedObject"].apply(lambda x: x.get("itemid") if x else None)
    df["severity"] = df["relatedObject"].apply(lambda x: x.get("priority") if x else None)

    df.rename(columns={
        "clock": "Date/Time",
        "devicename": "Host Name",
        "deviceid": "Device ID",
        "objectid": "Item ID",
        "name": "Event Name",
        "severity": "Severity"
    }, inplace=True)

    SEVERITY_MAP = {
    "0": "Not classified",
    "1": "Information",
    "2": "Warning",
    "3": "Average",
    "4": "High",
    "5": "Disaster"
    }
    df["Severity"] = df["Severity"].astype(str).map(SEVERITY_MAP)


    return df

# Streamlit App Configuration

st.set_page_config(page_title="Zabbix Problem Events Dashboard", 
                   layout="wide",
                   page_icon="./zabbix_icon.svg")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Choose a view:", [
    "10-Week Summary", 
    "Top 20 Host",
    "Top 20 Events",
    "All Events"
])


if page == "All Events":


    # Week selector
    iso_week = week_selector()
    if iso_week is None:
        iso_week = datetime.now().strftime("%G-W%V")
        st.info("No week selected. Defaulting to current week.")
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
    #st.dataframe(df[["Date/Time", "Host Name", "Device ID", "Item ID", "Event Name"]].reset_index(drop=True),height=800)

    st.dataframe(
    df[["Date/Time", "Host Name", "Device ID", "Item ID", "Event Name", "Severity"]].reset_index(drop=True),
    height=800
    )


# Page: Summary
elif page == "Top 20 Host":
    st.title("Top 20 Host")

    # Week selector
    iso_week = week_selector()
    if iso_week is None:
        iso_week = datetime.now().strftime("%G-W%V")
        st.info("No week selected. Defaulting to current week.")
    print(iso_week)

    # Get Monday of the ISO week
    start_date = datetime.strptime(iso_week + "-1", "%G-W%V-%u")
    end_date = start_date + timedelta(days=6)
    start_time = int(start_date.timestamp())
    end_time = int((end_date + timedelta(days=1)).timestamp())  # end is exclusive

    df = getEvents(start_time, end_time)

    summary_chart = df.groupby(["Host Name", "Event Name"]).size().reset_index(name="count").head(20)
    summary_chart.sort_values(by="count", ascending=False, inplace=True)


    summary = df.groupby("Host Name").size().reset_index(name="Event Count").head(20)
    summary.sort_values(by="Event Count", ascending=False, inplace=True)
    st.dataframe(summary.reset_index(drop=True), height=800)


    chart = alt.Chart(summary_chart).mark_bar().encode(
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

elif page == "Top 20 Events":
    st.title("Top 20 Events by Item ID")

    # Week selector
    iso_week = week_selector()
    if iso_week is None:
        iso_week = datetime.now().strftime("%G-W%V")
        st.info("No week selected. Defaulting to current week.")

    # Get time range
    start_date = datetime.strptime(iso_week + "-1", "%G-W%V-%u")
    end_date = start_date + timedelta(days=6)
    start_time = int(start_date.timestamp())
    end_time = int((end_date + timedelta(days=1)).timestamp())

    # Fetch events
    with st.spinner("Fetching events..."):
        df = getEvents(start_time, end_time)

    # Group and summarize
    top_items = (
        df.groupby(["Item ID", "Event Name"])
        .size()
        .reset_index(name="count")
        .sort_values(by="count", ascending=False)
        .head(20)
    )

    # Display table
    st.dataframe(top_items.reset_index(drop=True), height=600)

    # Optional: Add bar chart
    chart = alt.Chart(top_items).mark_bar().encode(
        x=alt.X("Item ID:N", sort="-y", title="Item ID"),
        y=alt.Y("count:Q", title="Event Count"),
        color="Event Name:N",
        tooltip=["Item ID", "Event Name", "count"]
    ).properties(
        width=800,
        height=400,
        title="Top 20 Events by Item ID"
    )

    st.altair_chart(chart, use_container_width=True)

elif page == "10-Week Summary":
    st.title("10-Week Event Summary")

    now = datetime.now()
    weekly_stats = []

    with st.spinner("Fetching 10 weeks of data..."):
        for i in range(10):
            week_start = now - timedelta(weeks=i, days=now.weekday())
            week_end = week_start + timedelta(days=7)
            start_time = int(week_start.timestamp())
            end_time = int(week_end.timestamp())

            df = getEvents(start_time, end_time)

            weekly_stats.append({
                "Week": week_start.strftime("%G-W%V"),
                "Total Events": len(df),
                "Unique Events": df["Event Name"].nunique(),
                "Hosts with Events": df["Host Name"].nunique()
            })

    summary_df = pd.DataFrame(weekly_stats).sort_values("Week")

    

    # Melt for Altair
    melted = summary_df.melt(id_vars="Week", 
                             value_vars=["Total Events", "Unique Events", "Hosts with Events"],
                             var_name="Metric", value_name="Count")

    chart = alt.Chart(melted).mark_line(point=True).encode(
        x=alt.X("Week:N", title="ISO Week"),
        y=alt.Y("Count:Q"),
        color="Metric:N",
        tooltip=["Week", "Metric", "Count"]
    ).properties(
        width=900,
        height=400,
        title="Weekly Trends: Events, Unique Events, and Hosts"
    )

    st.altair_chart(chart, use_container_width=True)

    st.dataframe(summary_df, height=500)

