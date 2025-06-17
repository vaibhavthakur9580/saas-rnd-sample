import stripe
from decouple import config

from . import date_utils

DJANGO_DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="", cast=str)
STRIPE_TEST_OVERRIDE = config("STRIPE_TEST_OVERRIDE", default=False, cast=bool)

if "sk_test" in STRIPE_SECRET_KEY and not DJANGO_DEBUG and not STRIPE_TEST_OVERRIDE:
    raise ValueError("Invalid stripe key for prod")

stripe.api_key = STRIPE_SECRET_KEY

def serialize_subscription_data(subscription_response):
    """
    Serialize subscription data with proper error handling for missing attributes.
    Fixed to properly extract period dates from subscription items.
    """
    if not hasattr(subscription_response, 'status'):
        raise ValueError("Invalid subscription object: missing status")

    status = subscription_response.status

    current_period_start = None
    current_period_end = None

    # First, try to get from the top-level subscription object (for older Stripe API versions)
    if hasattr(subscription_response, 'current_period_start') and subscription_response.current_period_start is not None:
        current_period_start = date_utils.timestamp_as_datetime(subscription_response.current_period_start)

    if hasattr(subscription_response, 'current_period_end') and subscription_response.current_period_end is not None:
        current_period_end = date_utils.timestamp_as_datetime(subscription_response.current_period_end)

    # Check within the first subscription item (this is where the data actually is in modern Stripe API)
    if hasattr(subscription_response, 'items') and \
       hasattr(subscription_response.items, 'data') and \
       len(subscription_response.items.data) > 0:
        
        first_item = subscription_response.items.data[0]
        
        # Always check the items for period dates since that's where they are in the current API
        if hasattr(first_item, 'current_period_start') and first_item.current_period_start is not None:
            current_period_start = date_utils.timestamp_as_datetime(first_item.current_period_start)
            
        if hasattr(first_item, 'current_period_end') and first_item.current_period_end is not None:
            current_period_end = date_utils.timestamp_as_datetime(first_item.current_period_end)

    # Handle cancel_at_period_end with default value
    cancel_at_period_end = getattr(subscription_response, 'cancel_at_period_end', False)

    # Add some debugging to see what we're returning
    # print(f"DEBUG: Serialized current_period_start: {current_period_start}")
    # print(f"DEBUG: Serialized current_period_end: {current_period_end}")

    return {
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
    }

def create_customer(
    name="",
    email="",
    metadata={},
    raw=False):
    response = stripe.Customer.create(
        name=name,
        email=email,
        metadata=metadata,
    )
    if raw:
        return response
    stripe_id = response.id
    return stripe_id

def create_product(name="",
    metadata={},
    raw=False):
    response = stripe.Product.create(
        name=name,
        metadata=metadata,
    )
    if raw:
        return response
    stripe_id = response.id
    return stripe_id

def create_price(currency="usd",
    unit_amount="9999",
    interval="month",
    product=None,
    metadata={},
    raw=False):
    if product is None:
        return None
    response = stripe.Price.create(
        currency=currency,
        unit_amount=unit_amount,
        recurring={"interval": interval},
        product=product,
        metadata=metadata
    )
    if raw:
        return response
    stripe_id = response.id
    return stripe_id

def start_checkout_session(customer_id,
    success_url="",
    cancel_url="",
    price_stripe_id="",
    raw=True):
    if not success_url.endswith("?session_id={CHECKOUT_SESSION_ID}"):
        success_url = f"{success_url}" + "?session_id={CHECKOUT_SESSION_ID}"
    response = stripe.checkout.Session.create(
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price_stripe_id, "quantity": 1}],
        mode="subscription",
    )
    if raw:
        return response
    return response.url

def get_checkout_session(stripe_id, raw=True):
    response = stripe.checkout.Session.retrieve(
        stripe_id
    )
    if raw:
        return response
    return response.url

def get_subscription(stripe_id, raw=True):
    response = stripe.Subscription.retrieve(
        stripe_id
    )
    if raw:
        return response
    return serialize_subscription_data(response)

def get_customer_active_subscriptions(customer_stripe_id):
    response = stripe.Subscription.list(
        customer=customer_stripe_id,
        status="active"
    )
    return response

def cancel_subscription(stripe_id, reason="", feedback="other", cancel_at_period_end=False, raw=True):
    if cancel_at_period_end:
        response = stripe.Subscription.modify(
            stripe_id,
            cancel_at_period_end=cancel_at_period_end,
            cancellation_details={
                "comment": reason,
                "feedback": feedback
            }
        )
    else:
        response = stripe.Subscription.cancel(
            stripe_id,
            cancellation_details={
                "comment": reason,
                "feedback": feedback
            }
        )
    if raw:
        return response
    return serialize_subscription_data(response)

def get_checkout_customer_plan(session_id):
    """
    Get checkout customer plan with improved error handling
    """
    try:
        checkout_r = get_checkout_session(session_id, raw=True)

        # Check if checkout session is completed
        if checkout_r.payment_status != 'paid':
            raise ValueError(f"Payment not completed. Status: {checkout_r.payment_status}")

        customer_id = checkout_r.customer
        sub_stripe_id = checkout_r.subscription

        if not sub_stripe_id:
            raise ValueError("No subscription found in checkout session")

        # Retrieve subscription with error handling
        sub_r = get_subscription(sub_stripe_id, raw=True)
        print(f"DEBUG: Raw Stripe Subscription Object: {sub_r}") # Add this line
        print(f"DEBUG: sub_r.current_period_start: {getattr(sub_r, 'current_period_start', 'Not Found')}") # Add this line
        print(f"DEBUG: sub_r.current_period_end: {getattr(sub_r, 'current_period_end', 'Not Found')}") # Add this line


        # Check subscription status
        if sub_r.status in ['incomplete', 'incomplete_expired']:
            raise ValueError(f"Subscription is incomplete. Status: {sub_r.status}")

        # Get plan information - handle both old and new Stripe API formats
        sub_plan = None
        if hasattr(sub_r, 'plan') and sub_r.plan:
            sub_plan = sub_r.plan
        elif hasattr(sub_r, 'items') and sub_r.items.data:
            # For newer Stripe API, get price from subscription items
            sub_plan = sub_r.items.data[0].price

        if not sub_plan:
            raise ValueError("Unable to retrieve subscription plan information")

        subscription_data = serialize_subscription_data(sub_r)

        data = {
            "customer_id": customer_id,
            "plan_id": sub_plan.id,
            "sub_stripe_id": sub_stripe_id,
            **subscription_data,
        }
        return data

    except stripe.error.StripeError as e:
        raise ValueError(f"Stripe API error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error processing checkout: {str(e)}")