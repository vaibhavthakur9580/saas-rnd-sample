import helpers.billing
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponseBadRequest
import logging

from subscriptions.models import SubscriptionPrice, Subscription, UserSubscription

User = get_user_model()
logger = logging.getLogger(__name__)

BASE_URL = settings.BASE_URL

def product_price_redirect_view(request, price_id=None, *args, **kwargs):
    request.session['checkout_subscription_price_id'] = price_id
    return redirect("stripe-checkout-start")

@login_required
def checkout_redirect_view(request):
    checkout_subscription_price_id = request.session.get("checkout_subscription_price_id")
    try:
        obj = SubscriptionPrice.objects.get(id=checkout_subscription_price_id)
    except:
        obj = None
    if checkout_subscription_price_id is None or obj is None:
        return redirect("pricing")
    customer_stripe_id = request.user.customer.stripe_id
    success_url_path = reverse("stripe-checkout-end")
    pricing_url_path = reverse("pricing")
    success_url = f"{BASE_URL}{success_url_path}"
    cancel_url= f"{BASE_URL}{pricing_url_path}"
    price_stripe_id = obj.stripe_id
    url = helpers.billing.start_checkout_session(
        customer_stripe_id,
        success_url=success_url,
        cancel_url=cancel_url,
        price_stripe_id=price_stripe_id,
        raw=False
    )
    return redirect(url)

def checkout_finalize_view(request):
    session_id = request.GET.get('session_id')

    if not session_id:
        messages.error(request, "Invalid checkout session.")
        return redirect("pricing")

    try:
        checkout_data = helpers.billing.get_checkout_customer_plan(session_id)
    except ValueError as e:
        logger.error(f"Checkout processing error: {str(e)}")
        messages.error(request, "There was an issue processing your payment. Please contact support if this persists.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Unexpected error during checkout: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please contact support.")
        return redirect("pricing")

    plan_id = checkout_data.pop('plan_id')
    customer_id = checkout_data.pop('customer_id')
    sub_stripe_id = checkout_data.pop("sub_stripe_id")
    subscription_data = {**checkout_data}

    try:
        sub_obj = Subscription.objects.get(subscriptionprice__stripe_id=plan_id)
    except Subscription.DoesNotExist:
        logger.error(f"Subscription not found for plan_id: {plan_id}")
        messages.error(request, "Subscription plan not found. Please contact support.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Error retrieving subscription: {str(e)}")
        sub_obj = None

    try:
        user_obj = User.objects.get(customer__stripe_id=customer_id)
    except User.DoesNotExist:
        logger.error(f"User not found for customer_id: {customer_id}")
        messages.error(request, "User account not found. Please contact support.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Error retrieving user: {str(e)}")
        user_obj = None

    _user_sub_exists = False
    updated_sub_options = {
        "subscription": sub_obj,
        "stripe_id": sub_stripe_id,
        "user_cancelled": False,
        **subscription_data,
    }

    try:
        _user_sub_obj = UserSubscription.objects.get(user=user_obj)
        _user_sub_exists = True
    except UserSubscription.DoesNotExist:
        try:
            _user_sub_obj = UserSubscription.objects.create(
                user=user_obj, 
                **updated_sub_options
            )
        except Exception as e:
            logger.error(f"Error creating user subscription: {str(e)}")
            _user_sub_obj = None
    except Exception as e:
        logger.error(f"Error retrieving user subscription: {str(e)}")
        _user_sub_obj = None

    if None in [sub_obj, user_obj, _user_sub_obj]:
        return HttpResponseBadRequest("There was an error with your account, please contact us.")

    if _user_sub_exists:
        # cancel old sub
        old_stripe_id = _user_sub_obj.stripe_id
        same_stripe_id = sub_stripe_id == old_stripe_id
        if old_stripe_id is not None and not same_stripe_id:
            try:
                helpers.billing.cancel_subscription(old_stripe_id, reason="Auto ended, new membership", feedback="other")
            except Exception as e:
                logger.warning(f"Failed to cancel old subscription {old_stripe_id}: {str(e)}")
                # Don't fail the entire process if old subscription cancellation fails
        
        # assign new sub
        try:
            for k, v in updated_sub_options.items():
                setattr(_user_sub_obj, k, v)
            _user_sub_obj.save()
        except Exception as e:
            logger.error(f"Error updating user subscription: {str(e)}")
            messages.error(request, "Error updating subscription. Please contact support.")
            return redirect("pricing")

    messages.success(request, "Success! Thank you for joining.")
    return redirect(_user_sub_obj.get_absolute_url())