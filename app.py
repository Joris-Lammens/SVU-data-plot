
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="RheaLyo™ Mono Freeze-Dryer data plotter", layout="wide")
LOG_FILE = "usage_log.csv"

import hashlib

def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()


st.sidebar.header("Access")

access_code = st.sidebar.text_input(
    "Enter your personal access code",
    type="password"
)

if not access_code:
    st.warning("Please enter your personal access code to use the app.")
    st.stop()

access_hash = hash_code(access_code)

USER_ACCESS = dict(st.secrets["users"])

if access_hash not in USER_ACCESS:
    st.error("Invalid access code.")
    st.stop()

user_email = USER_ACCESS[access_hash]

st.sidebar.success(f"Logged in as {user_email}")

def log_event(user, event, details=""):
    log_row = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user": user,
        "event": event,
        "details": details
    }])

    if Path(LOG_FILE).exists():
        log_row.to_csv(LOG_FILE, mode="a", header=False, index=False)
    else:
        log_row.to_csv(LOG_FILE, index=False)

st.title("RheaLyo™ Mono Freeze-Dryer data plotter")

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])


if uploaded_file is not None:
    if st.session_state.get("last_uploaded_file") != uploaded_file.name:
        log_event(user_email, "uploaded_file", uploaded_file.name)
        st.session_state["last_uploaded_file"] = uploaded_file.name

    df = pd.read_csv(uploaded_file)


    df["LocalTime"] = pd.to_datetime(df["LocalTime"])
    df["RelativeTime_s"] = (df["LocalTime"] - df["LocalTime"].min()).dt.total_seconds()
    df["RelativeTime_min"] = df["RelativeTime_s"] / 60

    def get_signal(dataframe, name_part):
        return dataframe[
            dataframe["DeviceDescription"]
            .str.contains(name_part, case=False, na=False)
        ].sort_values("RelativeTime_min")

    gas_temp = get_signal(df, "gas")
    vial_temp = get_signal(df, "vial")
    pirani = get_signal(df, "pirani")
    capacitance = get_signal(df, "capacitance")
    heater = get_signal(df, "heater")

    max_time = float(df["RelativeTime_min"].max())

    st.sidebar.header("Plot settings")

    x_min, x_max = st.sidebar.slider(
        "Time range (minutes)",
        min_value=0.0,
        max_value=max_time,
        value=(0.0, min(25.0, max_time))
    )

    temp_min, temp_max = st.sidebar.slider(
        "Temperature axis range",
        min_value=0,
        max_value=400,
        value=(50, 320)
    )

    right_min, right_max = st.sidebar.slider(
        "Pressure / heater axis range",
        min_value=0,
        max_value=100,
        value=(0, 20)
    )

    show_gas = st.sidebar.checkbox("Gas temperature", value=True)
    show_vial = st.sidebar.checkbox("Vial temperature", value=True)
    show_pirani = st.sidebar.checkbox("Pirani", value=True)
    show_capacitance = st.sidebar.checkbox("Capacitance", value=True)
    show_heater = st.sidebar.checkbox("Heater", value=True)

    fig, ax_left = plt.subplots(figsize=(12, 6))

    if show_gas:
        ax_left.plot(
            gas_temp["RelativeTime_min"],
            gas_temp["Value"],
            label="Gas temperature (K)",
            linewidth=1.5
        )

    if show_vial:
        ax_left.plot(
            vial_temp["RelativeTime_min"],
            vial_temp["Value"],
            label="Vial temperature (K)",
            linewidth=1.5
        )

    ax_left.set_xlabel("Time (minutes)")
    ax_left.set_ylabel("Temperature (K)")
    ax_left.set_xlim(x_min, x_max)
    ax_left.set_ylim(temp_min, temp_max)
    ax_left.grid(True)

    ax_right = ax_left.twinx()

    if show_pirani:
        ax_right.plot(
            pirani["RelativeTime_min"],
            pirani["Value"],
            label="Pirani (Pa)",
            linewidth=1.5,
            color="m",
            linestyle=":"
        )

    if show_capacitance:
        ax_right.plot(
            capacitance["RelativeTime_min"],
            capacitance["Value"],
            label="Capacitance (Pa)",
            linewidth=1.5,
            color="c",
            linestyle=":"
        )

    if show_heater:
        ax_right.plot(
            heater["RelativeTime_min"],
            heater["Value"],
            label="Heater (%)",
            linewidth=1.5,
            color="r",
            linestyle="-"
        )

    ax_right.set_ylabel("Pressure (Pa) / Heater (%)")
    ax_right.set_ylim(right_min, right_max)

    left_lines, left_labels = ax_left.get_legend_handles_labels()
    right_lines, right_labels = ax_right.get_legend_handles_labels()

    ax_left.legend(
        left_lines + right_lines,
        left_labels + right_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=4
    )

    plt.tight_layout()

    st.pyplot(fig)

    image_buffer = BytesIO()
    fig.savefig(image_buffer, format="png", dpi=300, bbox_inches="tight")
    image_buffer.seek(0)

    st.download_button(
        label="Download plot as PNG",
        data=image_buffer,
        file_name="run_plot.png",
        mime="image/png"
    )

    st.subheader("Preview data")
    st.dataframe(df.head())
else:
    st.info("Upload a CSV file to create the plot.")

st.info(
    """
    **Disclaimer**

    The developer makes no warranties and disclaims all liability for the accuracy, use, or consequences of data exported using the provided software. 
    The software is provided "as is".

    Please verify all results before using them for reporting, decision-making, validation,
    or regulatory documentation.
    """
)


if user_email == "joris.lammens@rheavita.com":
    st.subheader("Usage log")

    if Path(LOG_FILE).exists():
        log_df = pd.read_csv(LOG_FILE)
        st.dataframe(log_df)
    else:
        st.info("No usage logged yet.")
