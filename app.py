import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
import smtplib
from email.message import EmailMessage
import hashlib


st.set_page_config(
    page_title="RheaLyo™ Mono Freeze-Dryer data plotter",
    layout="wide"
)


# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------

def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()


def send_notify_email(user, event, details=""):
    """
    Sends a usage notification email.

    Requires Streamlit secrets:

    [email]
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "your_gmail_address@gmail.com"
    sender_password = "your_gmail_app_password"
    notify_to = "operations@rheavita.com"
    """
    try:
        msg = EmailMessage()
        msg["Subject"] = f"RheaLyo data plotter usage: {event}"
        msg["From"] = st.secrets["email"]["sender_email"]
        msg["To"] = st.secrets["email"]["notify_to"]

        body = f"""
RheaLyo™ Mono Freeze-Dryer data plotter usage notification

Timestamp: {datetime.now().isoformat(timespec="seconds")}
User: {user}
Event: {event}
Details: {details}
"""

        msg.set_content(body)

        with smtplib.SMTP(
            st.secrets["email"]["smtp_server"],
            int(st.secrets["email"]["smtp_port"])
        ) as server:
            server.starttls()
            server.login(
                st.secrets["email"]["sender_email"],
                st.secrets["email"]["sender_password"]
            )
            server.send_message(msg)

    except Exception as e:
        st.sidebar.warning(f"Email notification failed: {e}")


def get_signal(dataframe, name_part):
    return dataframe[
        dataframe["DeviceDescription"]
        .str.contains(name_part, case=False, na=False)
    ].sort_values("RelativeTime_min")


# -------------------------------------------------------------------
# Access control
# -------------------------------------------------------------------

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
    send_notify_email(
        "unknown",
        "invalid_access_code",
        "Someone entered an invalid access code"
    )
    st.error("Invalid access code.")
    st.stop()

user_email = USER_ACCESS[access_hash]

st.sidebar.success(f"Logged in as {user_email}")

if "opened_email_sent" not in st.session_state:
    send_notify_email(user_email, "opened_app", "App session started")
    st.session_state["opened_email_sent"] = True


# -------------------------------------------------------------------
# Main app
# -------------------------------------------------------------------

st.title("RheaLyo™ Mono Freeze-Dryer data plotter")

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

st.info(
    """
    **Disclaimer**

    The developer makes no warranties and disclaims all liability for the accuracy, use,
    or consequences of data exported using the provided software.

    The software is provided "as is".

    Please verify all results before using them for reporting, decision-making,
    validation, or regulatory documentation.
    """
)

if uploaded_file is not None:
    if st.session_state.get("last_uploaded_file") != uploaded_file.name:
        send_notify_email(user_email, "uploaded_file", uploaded_file.name)
        st.session_state["last_uploaded_file"] = uploaded_file.name

    df = pd.read_csv(uploaded_file)

    required_columns = ["LocalTime", "DeviceDescription", "Value"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        st.error(
            "The uploaded CSV is missing required column(s): "
            + ", ".join(missing_columns)
        )
        st.stop()

    df["LocalTime"] = pd.to_datetime(df["LocalTime"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

    df = df.dropna(subset=["LocalTime", "Value", "DeviceDescription"])

    if df.empty:
        st.error("No valid data found after parsing LocalTime and Value.")
        st.stop()

    df["RelativeTime_s"] = (
        df["LocalTime"] - df["LocalTime"].min()
    ).dt.total_seconds()
    df["RelativeTime_min"] = df["RelativeTime_s"] / 60

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

    if show_gas and not gas_temp.empty:
        ax_left.plot(
            gas_temp["RelativeTime_min"],
            gas_temp["Value"],
            label="Gas temperature (K)",
            linewidth=1.5
        )

    if show_vial and not vial_temp.empty:
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

    if show_pirani and not pirani.empty:
        ax_right.plot(
            pirani["RelativeTime_min"],
            pirani["Value"],
            label="Pirani (Pa)",
            linewidth=1.5,
            color="m",
            linestyle=":"
        )

    if show_capacitance and not capacitance.empty:
        ax_right.plot(
            capacitance["RelativeTime_min"],
            capacitance["Value"],
            label="Capacitance (Pa)",
            linewidth=1.5,
            color="c",
            linestyle=":"
        )

    if show_heater and not heater.empty:
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

    if left_lines or right_lines:
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

    def notify_download():
        send_notify_email(user_email, "downloaded_plot", "run_plot.png")

    st.download_button(
        label="Download plot as PNG",
        data=image_buffer,
        file_name="run_plot.png",
        mime="image/png",
        on_click=notify_download
    )

    st.subheader("Preview data")
    st.dataframe(df.head())

else:
    st.info("Upload a CSV file to create the plot.")
