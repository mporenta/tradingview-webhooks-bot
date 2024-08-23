import ib_insync
import time
from ib_insync import IB, util, MarketOrder
import threading

# Delay to allow time for port forwarding
time.sleep(40)

# Initialize the connection to IB Gateway
ib = IB()
try:
    ib.connect('127.0.0.1', 4002, clientId=2)
except Exception as e:
    print(f"Failed to connect to IB Gateway: {e}")
    exit(1)

# Set a flag to store the initial portfolio value
initial_portfolio_value = None
loss_threshold = -0.01  # Set threshold for 1% loss

def calculate_pnl(account_summary):
    """
    Calculate the PnL based on the initial portfolio value and the current portfolio value.
    """
    global initial_portfolio_value
    for summary in account_summary:
        if summary.tag == 'NetLiquidation':
            current_value = float(summary.value)
            if initial_portfolio_value is None:
                initial_portfolio_value = current_value
            pnl_percentage = (current_value - initial_portfolio_value) / initial_portfolio_value
            return pnl_percentage
    return 0.0

def on_update_event():
    """
    This function gets triggered whenever the IB Gateway sends an update.
    It monitors the portfolio's profit and loss.
    """
    global initial_portfolio_value
    try:
        account_summary = ib.accountSummary()
        pnl_percentage = calculate_pnl(account_summary)

        print(f"Real-time Update - Current PnL: {pnl_percentage * 100:.2f}%")

        if pnl_percentage <= loss_threshold:
            print("Portfolio down 1% or more (via event)! Closing all positions...")
            close_all_positions()
    except Exception as e:
        print(f"Error in on_update_event: {e}")

def poll_portfolio():
    """
    Periodically poll the portfolio's profit and loss in case real-time events are missed.
    """
    global initial_portfolio_value
    while True:
        try:
            # Get the updated account summary
            account_summary = ib.accountSummary()
            pnl_percentage = calculate_pnl(account_summary)

            print(f"Polling - Current PnL: {pnl_percentage * 100:.2f}%")

            # If the portfolio is down more than 1%, close all positions
            if pnl_percentage <= loss_threshold:
                print("Portfolio down 1% or more (via polling)! Closing all positions...")
                close_all_positions()
                break
        except Exception as e:
            print(f"Error in poll_portfolio: {e}")
        # Sleep for 5 seconds before the next poll
        time.sleep(5)

def close_all_positions():
    """
    Close all open positions in the portfolio by sending market orders.
    """
    try:
        positions = ib.positions()
        for position in positions:
            contract = position.contract
            quantity = position.position

            # Send a market order to close the position
            order = MarketOrder('SELL', quantity)
            trade = ib.placeOrder(contract, order)
            print(f"Closing position: {contract.symbol}, Quantity: {quantity}")
            trade.waitUntilDone()
    except Exception as e:
        print(f"Error in close_all_positions: {e}")

# Bind the update event to the function
ib.updateEvent += on_update_event

# Run polling in a separate thread to avoid blocking the event loop
polling_thread = threading.Thread(target=poll_portfolio)
polling_thread.start()

# Run the IB event loop (this is needed for real-time updates to work)
try:
    ib.run()
except Exception as e:
    print(f"Error in IB event loop: {e}")

# Wait for the polling thread to finish
polling_thread.join()

# Disconnect from IB Gateway when done
ib.disconnect()
