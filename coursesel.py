from html.parser import HTMLParser
import urllib.request
import urllib.parse
import http.cookiejar
import logging
import json
import time
import sys
import getpass


logging.basicConfig(
    format='%(asctime)-15s %(message)s',
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

JACCOUNT_CAPTCHA_URL = 'https://jaccount.sjtu.edu.cn/jaccount/captcha'
JACCOUNT_POST_SUBMIT_URL = 'https://jaccount.sjtu.edu.cn/jaccount/ulogin'
# FIND_LESSON_TASKS_URL need to be changed every time
FIND_LESSON_TASKS_URL = 'http://coursesel.umji.sjtu.edu.cn/tpm/findLessonTasks_ElectTurn.action?jsonString=%7B%22isToTheTime%22%3Atrue%2C%22electTurnId%22%3A%2201AC989B-0562-474D-8D0D-5C687C3DBBCF%22%2C%22loadCourseGroup%22%3Atrue%2C%22loadElectTurn%22%3Atrue%2C%22loadCourseType%22%3Atrue%2C%22loadCourseTypeCredit%22%3Atrue%2C%22loadElectTurnResult%22%3Atrue%2C%22loadStudentLessonTask%22%3Atrue%2C%22loadPrerequisiteCourse%22%3Atrue%2C%22lessonCalendarWeek%22%3Atrue%2C%22loadLessonCalendarConflict%22%3Atrue%2C%22loadTermCredit%22%3Atrue%2C%22loadLessonTask%22%3Atrue%2C%22loadDropApprove%22%3Atrue%2C%22loadElectApprove%22%3Atrue%7D'
# Currently, FIND_ALL_ELECT_CLASS_NOTIFY_VACANCY_URL is useless, but let's add it to act like a web browser
FIND_ALL_ELECT_CLASS_NOTIFY_VACANCY_URL = 'http://coursesel.umji.sjtu.edu.cn/tpm/findAll_ElectClassNotifyVacancy.action?_t=1525875395329&jsonString=%7B%22electTurnId%22%3A%2201AC989B-0562-474D-8D0D-5C687C3DBBCF%22%2C%22studentId%22%3A%2277D0533B-BA71-4385-8878-65B78636C1C6%22%2C%22isClosed%22%3A%220%22%7D'


def _find_attr(attr_list, attr_name, attr_value):
    if (attr_name, attr_value) in attr_list:
        return attr_value
    else:
        return None


def _get_attr(attr_list, attr_name):
    for attr_pair in attr_list:
        if attr_pair[0] == attr_name:
            return attr_pair[1]
    return None


class JaccountLoginParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._tag_form = False
        self._tag_title = False
        self.is_login_page = False
        self.sid_value = ''
        self.returl_value = ''
        self.se_value = ''
        self.v_value = ''
        self.client_value = ''
    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            if len(attrs) > 0:
                if _find_attr(attrs, 'id', 'form-input'):
                    self._tag_form = True
        if tag == 'input' and self._tag_form:
            if len(attrs) > 0:
                if _find_attr(attrs, 'name', 'sid'):
                    self.sid_value = _get_attr(attrs, 'value')
                elif _find_attr(attrs, 'name', 'returl'):
                    self.returl_value = _get_attr(attrs, 'value')
                elif _find_attr(attrs, 'name', 'se'):
                    self.se_value = _get_attr(attrs, 'value')
                elif _find_attr(attrs, 'name', 'v'):
                    self.v_value = _get_attr(attrs, 'value')
                elif _find_attr(attrs, 'name', 'client'):
                    self.client_value = _get_attr(attrs, 'value')
        if tag == 'title':
            self._tag_title = True
    def handle_endtag(self, tag):
        if tag == 'form':
            self._tag_form = False
        if tag == 'title':
            self._tag_title = False
    def handle_data(self, data):
        if self._tag_title:
            if 'SJTU Single Sign On' in data:
                self.is_login_page = True


def _login_jaccount_if_not(opener, page_html):
    jaccount_login_parser = JaccountLoginParser()
    jaccount_login_parser.feed(page_html.decode())
    if not jaccount_login_parser.is_login_page:
        logger.info('already login')
        return False
    captcha_img_byte = opener.open(JACCOUNT_CAPTCHA_URL).read()
    with open('captcha.jpg', 'wb') as captcha_img:
        captcha_img.write(captcha_img_byte)
    jaccount_username = input('Please input jAccount username: ')
    jaccount_password = getpass.getpass('Please input jAccount password: ')
    captcha_input = input('Please input captcha: ')
    post_form_data = {
        'sid': jaccount_login_parser.sid_value,
        'returl': jaccount_login_parser.returl_value,
        'se': jaccount_login_parser.se_value,
        'v': jaccount_login_parser.v_value,
        'client': jaccount_login_parser.client_value,
        'user': jaccount_username,
        'pass': jaccount_password,
        'captcha': captcha_input,
    }
    post_form_data_encoded = urllib.parse.urlencode(post_form_data).encode('utf-8')
    jaccount_login_request = urllib.request.Request(JACCOUNT_POST_SUBMIT_URL, post_form_data_encoded)
    opener.open(jaccount_login_request)
    logger.info('login post form sent')
    return True


def get_course_info(opener, course_code_list):
    coursesel_html = opener.open(FIND_LESSON_TASKS_URL).read()
    while _login_jaccount_if_not(opener, coursesel_html):
        coursesel_html = opener.open(FIND_LESSON_TASKS_URL).read()
    opener.open(FIND_ALL_ELECT_CLASS_NOTIFY_VACANCY_URL).read()
    return_dict = json.loads(coursesel_html.decode())
    for lesson in return_dict['data']['lessonTasks']:
        if lesson['courseShortName'] in course_code_list:
            student_num = int(lesson['studentNum'])
            max_num = int(lesson['maxNum'])
            if student_num < max_num:
                logger.info('S: {}, M: {}, Go and select the course {}!!!!!!!!!!!!!!!!!!'.format(student_num, max_num, lesson['courseShortName']))
            else:
                logger.info('S: {}, M: {}, Still no position in {}...'.format(student_num, max_num, lesson['courseShortName']))


if __name__ == '__main__':
    cookie = http.cookiejar.CookieJar()
    handler = urllib.request.HTTPCookieProcessor(cookie)
    opener = urllib.request.build_opener(handler)

    while True:
        cur_time = time.time()
        get_course_info(opener, ['VR102'])
        logger.info('Cost time: {}'.format(time.time() - cur_time))



'''
http://coursesel.umji.sjtu.edu.cn/tpm/findLessonTasks_ElectTurn.action?jsonString=%7B%22isToTheTime%22%3Afalse%2C%22electTurnId%22%3A%2201AC989B-0562-474D-8D0D-5C687C3DBBCF%22%2C%22loadCourseGroup%22%3Atrue%2C%22loadElectTurn%22%3Atrue%2C%22loadCourseType%22%3Atrue%2C%22loadCourseTypeCredit%22%3Atrue%2C%22loadElectTurnResult%22%3Atrue%2C%22loadStudentLessonTask%22%3Atrue%2C%22loadPrerequisiteCourse%22%3Atrue%2C%22lessonCalendarWeek%22%3Atrue%2C%22loadLessonCalendarConflict%22%3Atrue%2C%22loadTermCredit%22%3Atrue%2C%22loadLessonTask%22%3Atrue%2C%22loadDropApprove%22%3Atrue%2C%22loadElectApprove%22%3Atrue%7D
'''
