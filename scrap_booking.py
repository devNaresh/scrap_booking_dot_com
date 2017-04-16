## WAP to scrap hotels data from Booking.com for given cities


import re
import time
import csv
import psycopg2

from datetime import datetime
from psycopg2.extensions import AsIs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from bs4.element import Tag


CITIES = ["Los Angeles, CA", "New York, NY", "Chicago, IL"]


def get_available_rooms(hotel_element):
    """ Return Number of Available rooms if data not found return zero """

    if not hotel_element.find(class_='b-button__text'):
        return "Not Available"
    rooms = hotel_element.find(class_='b-button__text').text.strip()
    if re.findall('\d+', rooms):
        return int(re.findall('\d+', rooms)[0])
    rooms = hotel_element.find(class_=re.compile('demand'))
    if rooms and re.findall('\d+', rooms.string.strip()):
        return int(re.findall('\d+', rooms.string.strip())[0])
    else:
        return 0


def get_booking_details(hotel_element):
    """ Return Tuple of Number of time room booked and booking timeframe
        if data not found return Data Not Found """

    if hotel_element.find(class_=re.compile("rollover-s1")):
        booking_data = hotel_element.find(class_=re.compile("rollover-s1")).string.strip()
        booking_data = re.findall('\d+', booking_data)
        if len(booking_data) > 1:
            return booking_data[0].encode('utf-8'), booking_data[1].encode('utf-8')
        else:
            return "Not Found", booking_data[0].encode('utf-8')
    else:
        return "Data Not Fouund", "Data Not Fouund"


def get_price(hotel_element):
    """ Return Tuple of Stikethrough Price and Discounted Price
            if data not found return Booking Not Available """

    if not hotel_element.find(class_=re.compile('smart_price_style')):
        return "Booking Not Available", "Booking Not Available"
    price = hotel_element.find(class_=re.compile('smart_price_style')).text.strip()
    price = re.findall('Rs\..\w+,\w+', price)
    if len(price) > 1:
        return price[0].encode('utf-8'), price[1].encode('utf-8')
    else:
        return price[0].encode('utf-8'), price[0].encode('utf-8')


def write_to_csv(hotels, city):
    """ As Name suggests this method writes data to csv file of city name """

    with open('{0}_hotels.csv'.format(city), 'wb+') as f:
        w = csv.DictWriter(f,
                           ["name", "stikethrough_price", "discounted_price", "available_rooms", "num_of_times_booked",
                            "booking_timeframe", "city_and_state"])
        w.writeheader()
        for x in hotels:
            w.writerow(x)


def main(cursor):
    driver = webdriver.Chrome()  # Open Webdriver(need chrome webdriver to be installed)

    for city in CITIES:
        driver.get("https://www.booking.com/")
        driver.find_element_by_css_selector("#ss").send_keys(city)  # Enter City Name

        # Wait until autosuggestion come and click on first suggestion
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="frm"]/div[2]/div/div[1]/ul[1]/li[1]')))
        driver.find_element_by_xpath('//*[@id="frm"]/div[2]/div/div[1]/ul[1]/li[1]').click()

        check_in_time = datetime.fromtimestamp(int(time.time())).strftime("%Y-%m-%d")
        check_out_time = datetime.fromtimestamp(int(time.time()) + 604800).strftime("%Y-%m-%d")

        # Waits for Datetime widget and select check In date
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="frm"]/div[3]/div/div[1]/div[1]/div[2]/div/div[2]/div[1]/div')))
        except TimeoutException:
            driver.find_element_by_xpath('//*[@id="frm"]/div[3]/div/div[1]/div[1]/div[2]').click()
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="frm"]/div[3]/div/div[1]/div[1]/div[2]/div/div[2]/div[1]/div')))
        table = driver.find_elements_by_xpath('//*[@id="frm"]/div[3]/div/div[1]/div[1]/div[2]/'
                                              'div/div[2]/div[2]/div[3]/div/div/div[1]/table//td')
        for x in table:
            if x.get_attribute("data-id") and datetime.fromtimestamp(int(x.get_attribute("data-id")[:-3])).strftime(
                    "%Y-%m-%d") == check_in_time:
                x.click()

        # Waits for Datetime widget and select check Out date
        driver.find_element_by_xpath('//*[@id="frm"]/div[3]/div/div[1]/div[2]/div[2]/div/div[1]/div/div[2]').click()

        WebDriverWait(driver, 20).until(EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="frm"]/div[3]/div/div[1]/div[2]/div[2]/div/div[2]/div[1]/div')))
        table = driver.find_elements_by_xpath('//*[@id="frm"]/div[3]/div/div[1]/div[2]/div[2]/div/div[2]/div[2]/'
                                              'div[3]/div/div/div[1]/table//td')
        for x in table:
            if x.get_attribute("data-id") and datetime.fromtimestamp(int(x.get_attribute("data-id")[:-3])).strftime(
                    "%Y-%m-%d") == check_out_time:
                x.click()

        # Click Search Button
        driver.find_element_by_css_selector('#frm > div.sb-searchbox__row.u-clearfix.sb-searchbox__footer.-last > '
                                            'button').click()

        # Filter for Available Hotel remove already booked hotels and Waits until filter completes
        driver.find_element_by_xpath('//*[@id="filter_out_of_stock"]/div[2]/a/div/span').click()
        WebDriverWait(driver, 20).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, 'div.sr-usp-overlay__container.is_stuck')))

        hotels_data = []  # List of Hotel Details
        while 1:
            page = driver.page_source
            soup = BeautifulSoup(page, "lxml")  # Use BeautifulSoup For scraping of data since selenium is slow
            hotel_tags = [x for x in soup.find(id='hotellist_inner').contents if
                          isinstance(x, Tag) and x.find(class_="sr-hotel__name")]  # Get list of Hotels

            # Create hotel dict with information and append to hotels list
            for hotel in hotel_tags:
                hotel_data = dict()
                hotel_data["name"] = hotel.find(class_="sr-hotel__name").string.strip().encode('utf-8')
                hotel_data["stikethrough_price"], hotel_data["discounted_price"] = get_price(hotel)
                hotel_data["available_rooms"] = get_available_rooms(hotel)
                hotel_data["num_of_times_booked"], hotel_data["booking_timeframe"] = get_booking_details(hotel)
                hotel_data["city_and_state"] = city
                hotels_data.append(hotel_data.copy())

            # Check if next page is available if not exit through while loop
            if not soup.find(class_=re.compile("paging-next")):
                break
            # Open next page
            driver.get("https://www.booking.com{0}".format(soup.find(class_=re.compile("paging-next")).attrs["href"]))
        write_to_csv(hotels_data, city)
        if cursor:
            for data in hotels_data:
                insert_statement = 'insert into hotels (%s) values %s'
                query = cursor.mogrify(insert_statement, (AsIs(','.join(data.keys())), tuple(data.values())))
                cursor.execute(query)
        time.sleep(5)
    print("Done")
    driver.close()


if __name__ == "__main__":
    try:
        conn = psycopg2.connect(database="practice", user="naresh", password="naresh", host="127.0.0.1", port="5432")
        print "Opened database successfully"
        cur = conn.cursor()
        main(cur)
        conn.commit()
        conn.close()
    except Exception as e:
        main(False)
