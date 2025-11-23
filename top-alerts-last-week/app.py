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
ZABBIX_AUTH_METHOD = os.getenv("ZABBIX_AUTH_METHOD")  # possible zabbix, external
print(f"Using Zabbix URL: {ZABBIX_URL}")
print(f"Using Zabbix Auth Method: {ZABBIX_AUTH_METHOD}")    


if ZABBIX_AUTH_METHOD == "zabbix":
    # Session state for login
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "zapi" not in st.session_state:
        st.session_state.zapi = None

if ZABBIX_AUTH_METHOD == "external":
    # Use token-based session for external auth
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_TOKEN}"})
    st.session_state.authenticated = True
    st.session_state.zapi = zapi

# used for external auth method (ZABBIX_AUTH_METHOD is "external")
def login(username, password):
    try:
        temp_zapi = ZabbixAPI(ZABBIX_URL)
        temp_zapi.login(user=username, password=password)
        print("Login successful.")

        # Check if user is in "reports" group
        user_info = temp_zapi.user.get(filter={"username": username}, selectUsrgrps=["name"])
        groups = [g["name"] for g in user_info[0]["usrgrps"]]
        #print(user_info[0]["username"])

        if "reports" in groups:
            print("Reports Access granted.")
            # Set session state user info
            #st.session_state.user_info = str(user_info[0]["user"]) + " " +  str(user_info[0]["surname"]) + " (" + str(user_info[0]["username"]) + ")"
            st.session_state.user_info = user_info
            # Use token-based session for reports group
            zapi = ZabbixAPI(ZABBIX_URL)
            zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_TOKEN}"})
            st.session_state.authenticated = True
            st.session_state.zapi = zapi
        else:
            print("Reports Access denied.")
            st.error("Access denied: You are not in the 'reports' group.")
    except Exception as e:
        st.error(f"Login failed: {e}")



# Default Time range
now = datetime.now()
start_time = int((now - timedelta(days=7)).timestamp())
end_time = int(now.timestamp())

@st.cache_data(ttl=6000)
def getEvents(start_time, end_time):
    zapi = st.session_state.zapi
    events = zapi.event.get(
        time_from=start_time,
        time_till=end_time,
        value=1,
        selectHosts=["hostid", "name"],
        selectRelatedObject="extend",
        sortfield=["clock"],
        selectTags="extend",
        sortorder="DESC"
    )

    df = pd.DataFrame(events)
    #print(df.head())


    df["clock"] = pd.to_datetime(pd.to_numeric(df["clock"]), unit="s")
    df["deviceid"] = df["hosts"].apply(lambda x: x[0]["hostid"] if isinstance(x, list) and x else None)
    df["devicename"] = df["hosts"].apply(lambda x: x[0]["name"] if isinstance(x, list) and x else None)
    df["itemid"] = df["relatedObject"].apply(lambda x: x.get("itemid") if x else None)
    df["severity"] = df["relatedObject"].apply(lambda x: x.get("priority") if x else None)
    df["tags"] = df["tags"].apply(
        lambda taglist: [f"{t['tag']}:{t['value']}" for t in taglist] if isinstance(taglist, list) else []
        )


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

if ZABBIX_AUTH_METHOD == "zabbix":
    if not st.session_state.authenticated:
        st.title("🔐 Zabbix Dashboard Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                login(username, password)
        st.stop()


# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Choose a report:", [
    "Last Week Top 20 Reports",
    "end..."
])

if ZABBIX_AUTH_METHOD == "zabbix":
    username_logged = st.session_state.user_info[0]["username"] + " " + st.session_state.user_info[0]["surname"] + " (" + st.session_state.user_info[0]["username"] + ")"
    st.sidebar.success(f"Logged in as: {username_logged}")
    #str(user_info[0]["user"]) + " " +  str(user_info[0]["surname"]) + " (" + str(user_info[0]["username"]) + ")"
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.zapi = None
        st.rerun()

if page == "Last Week Top 20 Reports":

    # Week selector
    iso_week = week_selector("Select Week")
    if iso_week is None:
        iso_week = datetime.now().strftime("%G-W%V")
        st.info("No week selected. Defaulting to current week.")
    # Get Monday of the ISO week
    start_date = datetime.strptime(iso_week + "-1", "%G-W%V-%u")
    end_date = start_date + timedelta(days=6)
    start_time = int(start_date.timestamp())
    end_time = int((end_date + timedelta(days=1)).timestamp())  # end is exclusive

    # Collect all unique tag:value pairs across events
    all_tags = []
    events_preview = getEvents(start_time, end_time)  # quick fetch for available tags
    for tags in events_preview["tags"]:
        all_tags.extend(tags)
    unique_tags = sorted(set(all_tags))

    selected_tags = st.multiselect(
        "Filter by Tag:Value pairs",
        options=unique_tags,
        default=[]  # start with none selected
    )


    # 🔽 Global severity filter
    SEVERITY_OPTIONS = ["Not classified", "Information", "Warning", "Average", "High", "Disaster"]
    selected_severities = st.multiselect(
        "Filter by Severity",
        options=SEVERITY_OPTIONS,
        default=SEVERITY_OPTIONS  # default: show all
    )



    # Tabs for different pages of reports
    tab1, tab2, tab3, tab4 = st.tabs([
    "10-Week Summary", 
    "Top 20 Host", 
    "Top 20 Events", 
    "All Events"
    ])
    with tab4:
        st.title("Zabbix Problem Events "  + f" ({iso_week})")
        df = getEvents(start_time, end_time)
        # Apply severity filter
        if selected_severities:
            df = df[df["Severity"].isin(selected_severities)]
        # Apply tag:value filter
        if selected_tags:
            df = df[df["tags"].apply(lambda taglist: any(t in taglist for t in selected_tags))]

        st.dataframe(df[["Date/Time", "Host Name", "Device ID", "Item ID", 
            "Event Name", "Severity"]].reset_index(drop=True),
        height=800
        )
    
    with tab2:
        st.title("Top 20 Hosts by Event Count " + f" ({iso_week})")

        # Fetch events
        with st.spinner("Fetching events..."):
            df = getEvents(start_time, end_time)
        # Apply severity filter
        if selected_severities:
            df = df[df["Severity"].isin(selected_severities)]
        if selected_tags:
            df = df[df["tags"].apply(lambda taglist: any(t in taglist for t in selected_tags))]
           
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

        st.altair_chart(chart, width='stretch')

    
    with tab3:
        st.title("Top 20 Events by Item ID " + f" ({iso_week})")

        # Fetch events
        with st.spinner("Fetching events..."):
            df = getEvents(start_time, end_time)
        # Apply severity filter
        if selected_severities:
            df = df[df["Severity"].isin(selected_severities)]
        if selected_tags:
            df = df[df["tags"].apply(lambda taglist: any(t in taglist for t in selected_tags))]
 
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

        st.altair_chart(chart, width='stretch')

    with tab1:
        st.title("10-Week Event Summary")

        now = datetime.now()
        weekly_stats = []

        with st.spinner("Fetching 10 weeks of data..."):
            for i in range(1, 11):  # Start from 1 to exclude current week
                week_start = now - timedelta(weeks=i, days=now.weekday())
                week_end = week_start + timedelta(days=7)
                start_time = int(week_start.timestamp())
                end_time = int(week_end.timestamp())

                df = getEvents(start_time, end_time)
                # Apply severity filter
                if selected_severities:
                    df = df[df["Severity"].isin(selected_severities)]
                if selected_tags:
                    df = df[df["tags"].apply(lambda taglist: any(t in taglist for t in selected_tags))]
 
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
            x=alt.X("Week:N", title="Week"),
            y=alt.Y("Count:Q"),
            #color="Metric:N",
            color=alt.Color("Metric:N", legend=None),
            tooltip=["Week", "Metric", "Count"]
        ).properties(
            width=900,
            height=400,
            title="Weekly Trends: Events, Unique Events, and Hosts"
        )

        st.altair_chart(chart, width='stretch')

        st.dataframe(summary_df, height=500)


    # Another page can be added here
    #elif page == "Report 2":
