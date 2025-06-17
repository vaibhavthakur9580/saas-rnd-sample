import helpers.billing
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.db import transaction
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
    except SubscriptionPrice.DoesNotExist:  # Fixed: specific exception instead of bare except
        obj = None
    except Exception as e:
        logger.error(f"Error retrieving subscription price: {str(e)}")
        obj = None
        
    if checkout_subscription_price_id is None or obj is None:
        return redirect("pricing")
        
    customer_stripe_id = request.user.customer.stripe_id
    success_url_path = reverse("stripe-checkout-end")
    pricing_url_path = reverse("pricing")
    success_url = f"{BASE_URL}{success_url_path}"
    cancel_url = f"{BASE_URL}{pricing_url_path}"
    price_stripe_id = obj.stripe_id
    
    url = helpers.billing.start_checkout_session(
        customer_stripe_id,
        success_url=success_url,
        cancel_url=cancel_url,
        price_stripe_id=price_stripe_id,
        raw=False
    )
    return redirect(url)

@transaction.atomic  # Added transaction for data consistency
def checkout_finalize_view(request):
    session_id = request.GET.get('session_id')

    if not session_id:
        messages.error(request, "Invalid checkout session.")
        return redirect("pricing")

    try:
        checkout_data = helpers.billing.get_checkout_customer_plan(session_id)
        
        # DEBUG: Log the checkout_data to see what we're getting
        logger.info(f"Checkout data received: {checkout_data}")
        
    except ValueError as e:
        logger.error(f"Checkout processing error: {str(e)}")
        messages.error(request, "There was an issue processing your payment. Please contact support if this persists.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Unexpected error during checkout: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please contact support.")
        return redirect("pricing")

    # Extract required fields
    plan_id = checkout_data.pop('plan_id')
    customer_id = checkout_data.pop('customer_id')
    sub_stripe_id = checkout_data.pop("sub_stripe_id")
    
    # The remaining data should include the period dates
    subscription_data = {**checkout_data}
    
    # DEBUG: Log what's in subscription_data
    logger.info(f"Subscription data for UserSubscription: {subscription_data}")

    # Get subscription object
    try:
        sub_obj = Subscription.objects.get(subscriptionprice__stripe_id=plan_id)
    except Subscription.DoesNotExist:
        logger.error(f"Subscription not found for plan_id: {plan_id}")
        messages.error(request, "Subscription plan not found. Please contact support.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Error retrieving subscription: {str(e)}")
        messages.error(request, "Database error. Please contact support.")
        return redirect("pricing")

    # Get user object
    try:
        user_obj = User.objects.get(customer__stripe_id=customer_id)
    except User.DoesNotExist:
        logger.error(f"User not found for customer_id: {customer_id}")
        messages.error(request, "User account not found. Please contact support.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Error retrieving user: {str(e)}")
        messages.error(request, "Database error. Please contact support.")
        return redirect("pricing")

    # Prepare subscription update data
    updated_sub_options = {
        "subscription": sub_obj,
        "stripe_id": sub_stripe_id,
        "user_cancelled": False,
        **subscription_data,  # This should include current_period_start and current_period_end
    }
    
    # DEBUG: Log the final update options
    logger.info(f"Updated subscription options: {updated_sub_options}")

    # Handle user subscription creation/update
    try:
        _user_sub_obj, created = UserSubscription.objects.get_or_create(
            user=user_obj,
            defaults=updated_sub_options
        )
        
        if not created:
            # User subscription exists, handle the update
            old_stripe_id = _user_sub_obj.stripe_id
            same_stripe_id = sub_stripe_id == old_stripe_id
            
            # Cancel old subscription if different
            if old_stripe_id is not None and not same_stripe_id:
                try:
                    helpers.billing.cancel_subscription(
                        old_stripe_id, 
                        reason="Auto ended, new membership", 
                        feedback="other"
                    )
                    logger.info(f"Cancelled old subscription: {old_stripe_id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel old subscription {old_stripe_id}: {str(e)}")
                    # Don't fail the entire process if old subscription cancellation fails
            
            # Update the subscription with new data
            for k, v in updated_sub_options.items():
                setattr(_user_sub_obj, k, v)
            _user_sub_obj.save()
            
            # DEBUG: Log the saved subscription
            logger.info(f"Updated UserSubscription - ID: {_user_sub_obj.id}, "
                       f"Period Start: {_user_sub_obj.current_period_start}, "
                       f"Period End: {_user_sub_obj.current_period_end}")
        else:
            # DEBUG: Log the created subscription
            logger.info(f"Created UserSubscription - ID: {_user_sub_obj.id}, "
                       f"Period Start: {_user_sub_obj.current_period_start}, "
                       f"Period End: {_user_sub_obj.current_period_end}")
            
    except Exception as e:
        logger.error(f"Error handling user subscription: {str(e)}")
        messages.error(request, "Error processing subscription. Please contact support.")
        return redirect("pricing")

    messages.success(request, "Success! Thank you for joining.")
    return redirect(_user_sub_obj.get_absolute_url())