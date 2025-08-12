from django.shortcuts import render, redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.apps import apps
from restaurant.models import Customer, Dish, Menu
from datetime import datetime, timedelta
from django.contrib import auth
import pytz 
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Avg, Count, Min
from django.db.models.functions import ExtractHour, ExtractWeek, ExtractYear, ExtractMonth, TruncDate
import json
import pandas as pd
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
import requests
from io import BytesIO
from django.contrib import messages

# Get the Table model from the apps registry
Table = apps.get_model('restaurant', 'Table')

def register(request):
    if request.method == "POST":  
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = User.objects.create_user(username=username, password=password)
        user.save()    
        return redirect('/')         
    return render(request, 'register.html')

def login(request):
    if request.method=="POST":
        username=request.POST.get('username')
        password=request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            request.session['userid']=username
            return redirect('/index')
            
    return render(request,'login.html') 

def logout(request):
    auth.logout(request)  # This properly handles both session and authentication
    return redirect('/')

def index(request): 
    if request.session.has_key('userid'):
        menu = Menu.objects.filter(userid=request.session['userid'])
        tables = Table.objects.all()
        
        if request.method == "POST":
            if request.POST.get('save') == "save":
                order_type = request.POST.get('order_type')
                t = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%d/%m/%y %I:%M %p")
                
                # Create customer record
                customer = Customer(
                    userid=request.session['userid'],
                    time=t,
                    amount=0,
                    total=0,  # Initialize total
                    order_type=order_type,
                    date=datetime.now(pytz.timezone('Asia/Kolkata'))  # Set the date
                )
                customer.save()
                
                # Handle table assignment for dine-in orders
                if order_type == 'dine-in':
                    table_number = request.POST.get('table_number')
                    if table_number:
                        try:
                            table = Table.objects.get(number=int(table_number))
                            if not table.is_occupied:
                                table.is_occupied = True
                                table.current_order = customer
                                table.save()
                            else:
                                # Handle case where table is already occupied
                                customer.delete()
                                context = {
                                    'menu': menu,
                                    'userdata': request.session['userid'],
                                    'tables': tables,
                                    'error': f'Table {table_number} is already occupied.'
                                }
                                return render(request, 'index.html', context)
                        except Table.DoesNotExist:
                            # Handle case where table doesn't exist
                            customer.delete()
                            context = {
                                'menu': menu,
                                'userdata': request.session['userid'],
                                'tables': tables,
                                'error': f'Table {table_number} does not exist.'
                            }
                            return render(request, 'index.html', context)
                
                # Process order items
                total = 0
                for menu_item in menu:
                    quantity = int(request.POST.get(menu_item.dishname, 0))
                    if quantity > 0:
                        dish = Dish(
                            oid=customer.id,
                            dname=menu_item.dishname,
                            dquantity=quantity,
                            damount=quantity * menu_item.dishprice
                        )
                        dish.save()
                        total += quantity * menu_item.dishprice
        
                customer.amount = total
                customer.total = total  # Set the total field
                customer.save()
                
                # For parcel orders, show receipt
                if order_type == 'parcel':
                    dishes = Dish.objects.filter(oid=customer.id)
                    return render(request, 'Recpt.html', {'customer': customer, 'dish': dishes})
            
                # For dine-in orders, redirect to tables view
                return redirect('/tables')
        
        # Get only unoccupied tables for the form
        available_tables = tables.filter(is_occupied=False)
        context = {
            'menu': menu,
            'userdata': request.session['userid'],
            'tables': available_tables
        }
        return render(request, 'index.html', context)
    else:
        return redirect('/')

def show(request):
    if request.session.has_key('userid'):
        customers = Customer.objects.filter(userid=request.session['userid']).order_by('-id')
        dishes = Dish.objects.all()
        tables = Table.objects.all()
        context = {
            'customer': customers,
            'dish': dishes,
            'tables': tables,
            'userdata': request.session['userid']
        }
        return render(request, 'show.html', context)
    else:
        return redirect('/')

def tables(request):
    if request.session.has_key('userid'):
        tables = Table.objects.all().order_by('number')
        for table in tables:
            if table.current_order:
                # Get dishes for the current order
                table.dishes = Dish.objects.filter(oid=table.current_order.id)
                # Calculate total for the current order
                table.order_total = sum(dish.damount for dish in table.dishes)
            else:
                table.dishes = []
                table.order_total = 0
        
        context = {
            'tables': tables,
            'userdata': request.session['userid']
        }
        return render(request, 'tables.html', context)
    else:
        return redirect('/')

def clear_table(request, table_number):
    if request.session.has_key('userid'):
        try:
            # Get the table with proper validation
            table = get_object_or_404(Table, number=table_number)
            
            if table.current_order:
                # Store the order and mark it as completed
                order = table.current_order
                order.status = 'completed'  # Add this field to Customer model if not exists
                order.save()
                
                # Clear the table
                table.is_occupied = False
                table.current_order = None
                table.save()
                
                # Add a success message
                messages.success(request, f'Table {table_number} has been cleared successfully.')
            
            # Always redirect back to tables view
            return redirect('/tables')
        except Table.DoesNotExist:
            messages.error(request, f'Table {table_number} not found.')
            return redirect('/tables')
    return redirect('/')

def print_bill(request, order_id):
    if request.session.has_key('userid'):
        try:
            # Get the order with proper validation
            customer = get_object_or_404(Customer, id=order_id, userid=request.session['userid'])
            dishes = Dish.objects.filter(oid=order_id)
            
            # Calculate total amount
            total_amount = sum(dish.damount for dish in dishes)
            
            # Get table information for dine-in orders
            table = None
            if customer.order_type == 'dine-in':
                try:
                    table = Table.objects.get(current_order=customer)
                except Table.DoesNotExist:
                    pass
            
            context = {
                'customer': customer,
                'dish': dishes,
                'total_amount': total_amount,
                'table': table,
                'userdata': request.session['userid']
            }
            return render(request, 'Recpt.html', context)
        except Customer.DoesNotExist:
            return redirect('/show')
    return redirect('/')

def additem(request):
    if request.session.has_key('userid'):
        if request.method == "POST":
            itemname = request.POST.get('itemname')
            itemprice = request.POST.get('itemprice')
            itemtype = request.POST.get('itemtype')
            menu = Menu(userid=request.session['userid'], dishname=itemname, dishprice=itemprice, dishtype=itemtype)
            menu.save()
            return redirect('/showitem')
        return render(request, 'additem.html', {'userdata': request.session['userid']})
    return redirect('/')

def showitem(request):
    if request.session.has_key('userid'):
        menu = Menu.objects.filter(userid=request.session['userid'])
        return render(request, 'showitem.html', {'menu': menu, 'userdata': request.session['userid']})
    return redirect('/')

def edititem(request, id):
    if request.session.has_key('userid'):
        menu = Menu.objects.get(id=id)
        if request.method == "POST":
            menu.dishname = request.POST.get('itemname')
            menu.dishprice = request.POST.get('itemprice')
            menu.dishtype = request.POST.get('itemtype')
            menu.save()
            return redirect('/showitem')
        return render(request, 'edititem.html', {'menu': menu, 'userdata': request.session['userid']})
    return redirect('/')

def deleteitem(request, dishname):
    if request.session.has_key('userid'):
        try:
            menu = Menu.objects.get(dishname=dishname, userid=request.session['userid'])
            menu.delete()
            return JsonResponse({'success': True})
        except Menu.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Item not found'})
    return JsonResponse({'success': False, 'message': 'Not authorized'})

def revenue(request):
    if request.session.has_key('userid'):
        # Get today's date
        today = datetime.now(pytz.timezone('Asia/Kolkata')).date()
        
        # Get all orders for today
        orders = Customer.objects.filter(
            userid=request.session['userid'],
            date__date=today
        ).order_by('-date')
        
        # Calculate total revenue and average order value
        total_revenue = orders.aggregate(Sum('amount'))['amount__sum'] or 0
        avg_order_value = orders.aggregate(Avg('amount'))['amount__avg'] or 0
        total_orders = orders.count()
        
        # Get order counts by type
        dine_in_count = orders.filter(order_type='dine-in').count()
        parcel_count = orders.filter(order_type='parcel').count()
        
        # Get hourly order distribution
        hourly_orders = orders.annotate(
            hour=ExtractHour('date')
        ).values('hour').annotate(
            count=Count('id'),
            revenue=Sum('amount')
        ).order_by('hour')
        
        # Prepare chart data
        chart_labels = []
        chart_data = []
        
        # Initialize data for all 24 hours
        hour_data = {i: 0 for i in range(24)}
        
        # Fill in actual data
        for entry in hourly_orders:
            hour_data[entry['hour']] = float(entry['revenue'] or 0)
        
        # Convert to lists for the chart
        for hour in range(24):
            chart_labels.append(f"{hour:02d}:00")
            chart_data.append(hour_data[hour])
        
        # Find peak hour revenue
        peak_hour_revenue = max(hour_data.values())
        
        # Prepare revenue data for table
        revenue_data = []
        for entry in hourly_orders:
            revenue_data.append({
                'date': f"{entry['hour']:02d}:00",
                'orders': entry['count'],
                'revenue': float(entry['revenue'] or 0),
                'avg_value': float(entry['revenue'] or 0) / entry['count'] if entry['count'] > 0 else 0
            })
        
        context = {
            'orders': orders,
            'total_revenue': total_revenue,
            'avg_order_value': avg_order_value,
            'total_orders': total_orders,
            'dine_in_count': dine_in_count,
            'parcel_count': parcel_count,
            'peak_hour_revenue': peak_hour_revenue,
            'chart_labels': json.dumps(chart_labels),
            'chart_data': json.dumps(chart_data),
            'revenue_data': revenue_data,
            'userdata': request.session['userid']
        }
        return render(request, 'revenue.html', context)
    return redirect('/')

def revenue_filter(request):
    if request.session.has_key('userid'):
        range_type = request.GET.get('range')
        custom_range = request.GET.get('custom_range')
        
        # Get current timezone
        timezone = pytz.timezone('Asia/Kolkata')  # Using correct timezone name for India
        end_date = datetime.now(timezone)
        
        if range_type == 'daily':
            # For daily view, show today's data
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1) - timedelta(microseconds=1)
            group_by = 'hour'
        elif range_type == 'monthly':
            start_date = end_date - timedelta(days=30)
            group_by = 'month'
        elif range_type == 'overall':
            # Get the date of the first order
            first_order = Customer.objects.filter(userid=request.session['userid']).order_by('date').first()
            if first_order:
                start_date = first_order.date
                # If the range is more than 365 days, group by month, otherwise group by day
                days_diff = (end_date.date() - start_date.date()).days
                group_by = 'month' if days_diff > 365 else 'day'
            else:
                # If no orders exist, show last 30 days
                start_date = end_date - timedelta(days=30)
                group_by = 'day'
        elif range_type == 'custom' and custom_range:
            try:
                # Parse custom date range
                start_str, end_str = custom_range.split(' - ')
                start_date = timezone.localize(datetime.strptime(start_str, '%Y-%m-%d')).replace(hour=0, minute=0, second=0, microsecond=0)
                
                # If end date is today, use current time, otherwise use end of day
                if end_str == datetime.now(timezone).strftime('%Y-%m-%d'):
                    end_date = datetime.now(timezone)
                else:
                    end_date = timezone.localize(datetime.strptime(end_str, '%Y-%m-%d')).replace(hour=23, minute=59, second=59, microsecond=999999)
                
                group_by = 'day'  # Show daily data for custom range
            except ValueError:
                return JsonResponse({'error': 'Invalid date format'})
        else:
            return JsonResponse({'error': 'Invalid range type'})
        
        # Get filtered orders
        orders = Customer.objects.filter(
            userid=request.session['userid'],
            date__range=(start_date, end_date)
        ).order_by('date')  # Added ordering for consistency
        
        # Calculate metrics
        total_revenue = orders.aggregate(Sum('amount'))['amount__sum'] or 0
        avg_order_value = orders.aggregate(Avg('amount'))['amount__avg'] or 0
        total_orders = orders.count()
        dine_in_count = orders.filter(order_type='dine-in').count()
        parcel_count = orders.filter(order_type='parcel').count()
        
        # Get time-based distribution
        if group_by == 'hour':
            time_distribution = orders.annotate(
                hour=ExtractHour('date')
            ).values('hour').annotate(
                count=Count('id'),
                revenue=Sum('amount')
            ).order_by('hour')
            
            # Initialize data for all 24 hours
            hour_data = {i: 0 for i in range(24)}
            
            # Fill in actual data
            for entry in time_distribution:
                hour_data[entry['hour']] = float(entry['revenue'] or 0)
            
            # Convert to lists for the chart
            chart_labels = [f"{hour:02d}:00" for hour in range(24)]
            chart_data = [hour_data[hour] for hour in range(24)]
            
            # Find peak hour revenue
            peak_hour_revenue = max(hour_data.values()) if hour_data else 0
            
            # Prepare revenue data for table
            revenue_data = []
            for entry in time_distribution:
                revenue_data.append({
                    'date': f"{entry['hour']:02d}:00",
                    'orders': entry['count'],
                    'revenue': float(entry['revenue'] or 0),
                    'avg_value': float(entry['revenue'] or 0) / entry['count'] if entry['count'] > 0 else 0
                })
        elif group_by == 'day':
            # For custom date range or overall (if less than 365 days), show daily data
            time_distribution = orders.annotate(
                day=TruncDate('date')
            ).values('day').annotate(
                count=Count('id'),
                revenue=Sum('amount')
            ).order_by('day')
            
            # Initialize data for all days in range
            days = []
            current = start_date
            while current.date() <= end_date.date():
                days.append(current.date())
                current += timedelta(days=1)
            
            day_data = {day: 0 for day in days}
            
            # Fill in actual data
            for entry in time_distribution:
                day_data[entry['day']] = float(entry['revenue'] or 0)
            
            # Convert to lists for the chart
            chart_labels = [day.strftime('%Y-%m-%d') for day in days]
            chart_data = [day_data[day] for day in days]
            
            # Find peak day revenue
            peak_hour_revenue = max(day_data.values()) if day_data else 0
            
            # Prepare revenue data for table
            revenue_data = []
            for entry in time_distribution:
                revenue_data.append({
                    'date': entry['day'].strftime('%Y-%m-%d'),
                    'orders': entry['count'],
                    'revenue': float(entry['revenue'] or 0),
                    'avg_value': float(entry['revenue'] or 0) / entry['count'] if entry['count'] > 0 else 0
                })
        else:
            # Monthly view or overall (if more than 365 days)
            time_distribution = orders.annotate(
                year=ExtractYear('date'),
                month=ExtractMonth('date')
            ).values('year', 'month').annotate(
                count=Count('id'),
                revenue=Sum('amount')
            ).order_by('year', 'month')
            
            # Initialize data structure for months
            month_data = {}
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            
            # Fill in actual data
            chart_labels = []
            chart_data = []
            
            for entry in time_distribution:
                month_label = f"{months[entry['month']-1]} {entry['year']}"
                chart_labels.append(month_label)
                chart_data.append(float(entry['revenue'] or 0))
                month_data[month_label] = {
                    'revenue': float(entry['revenue'] or 0),
                    'count': entry['count']
                }
            
            # Find peak month revenue
            peak_hour_revenue = max(chart_data) if chart_data else 0
            
            # Prepare revenue data for table
            revenue_data = []
            for label in chart_labels:
                data = month_data[label]
                revenue_data.append({
                    'date': label,
                    'orders': data['count'],
                    'revenue': data['revenue'],
                    'avg_value': data['revenue'] / data['count'] if data['count'] > 0 else 0
                })
        
        response_data = {
            'total_revenue': float(total_revenue),
            'avg_order_value': float(avg_order_value) if avg_order_value else 0,
            'total_orders': total_orders,
            'dine_in_count': dine_in_count,
            'parcel_count': parcel_count,
            'peak_hour_revenue': float(peak_hour_revenue),
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'revenue_data': revenue_data
        }
        
        return JsonResponse(response_data)
    return JsonResponse({'error': 'Not authorized'})

def export_revenue_excel(request):
    if request.session.has_key('userid'):
        # Create a new workbook and select the active sheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Revenue Report"
        
        # Add headers
        headers = ['Date', 'Time', 'Order Type', 'Amount']
        ws.append(headers)
        
        # Get all orders for the user
        orders = Customer.objects.filter(userid=request.session['userid']).order_by('-date')
        
        # Add data rows
        for order in orders:
            row = [
                order.date.strftime('%Y-%m-%d'),
                order.date.strftime('%H:%M:%S'),
                order.order_type.title(),
                order.amount
            ]
            ws.append(row)
        
        # Create response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=revenue_report.xlsx'
        
        # Save the workbook to the response
        wb.save(response)
        return response
    return redirect('/')

def send_whatsapp_report(request):
    if request.session.has_key('userid'):
        try:
            # Get today's orders
            today = datetime.now(pytz.timezone('Asia/Kolkata')).date()
            orders = Customer.objects.filter(
                userid=request.session['userid'],
                date__date=today
            )
            
            # Calculate metrics
            total_revenue = orders.aggregate(Sum('amount'))['amount__sum'] or 0
            order_count = orders.count()
            dine_in_count = orders.filter(order_type='dine-in').count()
            parcel_count = orders.filter(order_type='parcel').count()
            
            # Format message
            message = f"""*Daily Revenue Report*
Date: {today.strftime('%d/%m/%Y')}

Total Revenue: ₹{total_revenue}
Total Orders: {order_count}
Dine-in Orders: {dine_in_count}
Parcel Orders: {parcel_count}

Generated by TopTaste"""
            
            # URL encode the message
            encoded_message = requests.utils.quote(message)
            
            # Create WhatsApp URL
            whatsapp_url = f"https://wa.me/?text={encoded_message}"
            
            return JsonResponse({
                'success': True,
                'whatsapp_url': whatsapp_url
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    return JsonResponse({
        'success': False,
        'error': 'Not authorized'
    })

def view_order(request, id):
    if request.session.has_key('userid'):
        try:
            # Get the order with proper validation
            customer = get_object_or_404(Customer, id=id, userid=request.session['userid'])
            dishes = Dish.objects.filter(oid=id)
            
            # Get table information for dine-in orders
            table = None
            if customer.order_type == 'dine-in':
                try:
                    table = Table.objects.get(current_order=customer)
                except Table.DoesNotExist:
                    pass
            
            context = {
                'customer': customer,
                'dishes': dishes,
                'table': table,
                'userdata': request.session['userid']
            }
            return render(request, 'view_order.html', context)
        except Customer.DoesNotExist:
            messages.error(request, 'Order not found.')
            return redirect('/show')
    return redirect('/')

def edit_order(request, id):
    if request.session.has_key('userid'):
        try:
            # Get the order and its dishes
            customer = get_object_or_404(Customer, id=id, userid=request.session['userid'])
            dishes = Dish.objects.filter(oid=id)
            menu = Menu.objects.filter(userid=request.session['userid'])
            tables = Table.objects.filter(is_occupied=False)
            
            # Get current table if it's a dine-in order
            current_table = None
            if customer.order_type == 'dine-in':
                try:
                    current_table = Table.objects.get(current_order=customer)
                    # Include current table in available tables
                    tables = tables | Table.objects.filter(id=current_table.id)
                except Table.DoesNotExist:
                    pass
            
            if request.method == "POST":
                # Update order type
                new_order_type = request.POST.get('order_type')
                old_order_type = customer.order_type
                customer.order_type = new_order_type
                
                # Handle table assignment changes
                if old_order_type == 'dine-in':
                    # Clear old table if it exists
                    if current_table:
                        current_table.is_occupied = False
                        current_table.current_order = None
                        current_table.save()
                
                if new_order_type == 'dine-in':
                    table_number = request.POST.get('table_number')
                    if table_number:
                        try:
                            new_table = Table.objects.get(number=int(table_number))
                            if not new_table.is_occupied or (current_table and current_table.id == new_table.id):
                                new_table.is_occupied = True
                                new_table.current_order = customer
                                new_table.save()
                            else:
                                messages.error(request, f'Table {table_number} is already occupied.')
                                return redirect(f'/edit-order/{id}')
                        except Table.DoesNotExist:
                            messages.error(request, f'Table {table_number} does not exist.')
                            return redirect(f'/edit-order/{id}')
                
                # Delete existing dishes
                Dish.objects.filter(oid=id).delete()
                
                # Add updated dishes
                total = 0
                for menu_item in menu:
                    # Get quantity and convert to int, defaulting to 0 if empty or invalid
                    try:
                        quantity = int(request.POST.get(menu_item.dishname, '0') or '0')
                    except ValueError:
                        quantity = 0
                        
                    if quantity > 0:
                        dish = Dish(
                            oid=customer.id,
                            dname=menu_item.dishname,
                            dquantity=quantity,
                            damount=quantity * menu_item.dishprice
                        )
                        dish.save()
                        total += quantity * menu_item.dishprice
                
                # Ensure at least one item is selected
                if total == 0:
                    messages.error(request, 'Please select at least one item.')
                    return redirect(f'/edit-order/{id}')
                
                customer.amount = total
                customer.total = total
                customer.save()
                
                messages.success(request, 'Order updated successfully.')
                return redirect('/show')
            
            context = {
                'customer': customer,
                'dishes': dishes,
                'menu': menu,
                'tables': tables,
                'current_table': current_table,
                'userdata': request.session['userid']
            }
            return render(request, 'edit_order.html', context)
            
        except Customer.DoesNotExist:
            messages.error(request, 'Order not found.')
            return redirect('/show')
    return redirect('/')

def destroy(request, id):
    if request.session.has_key('userid'):
        try:
            # Get the order
            customer = get_object_or_404(Customer, id=id, userid=request.session['userid'])
            
            # If it's a dine-in order, free up the table
            if customer.order_type == 'dine-in':
                try:
                    table = Table.objects.get(current_order=customer)
                    table.is_occupied = False
                    table.current_order = None
                    table.save()
                except Table.DoesNotExist:
                    pass
            
            # Delete associated dishes first (to maintain referential integrity)
            Dish.objects.filter(oid=id).delete()
            
            # Delete the order
            customer.delete()
            
            messages.success(request, 'Order deleted successfully.')
            return redirect('/show')
            
        except Customer.DoesNotExist:
            messages.error(request, 'Order not found.')
            return redirect('/show')
    return redirect('/') 