from cv_bridge import CvBridge, CvBridgeError
from duckietown_msgs.msg import (AntiInstagramTransform, BoolStamped, Segment,
    SegmentList, Vector2D)
from duckietown_utils.instantiate_utils import instantiate
from duckietown_utils.jpg import image_cv_from_jpg
from sensor_msgs.msg import CompressedImage, Image
from std_msgs import Bool

import cv2
import rospy
import time
import threading
import numpy as np

BG_SAMPLE = 1000
BG_WIDTH = (1296*972)*3

class BotDetectorNode(object):
	"""docstring for BotDetectorNode"""
	def __init__(self):
		self.node_name = "BotDetectorNode"

		#Thread Lock
		self.thread_lock = threading.lock()

		#Constructor of bot detector
		self.bridge = CvBridge()

		self.active  = True

		self.stats = Stats()

		#Only be verbose every 10 cycles
		self.intermittent_intervel = 100
		self.intermittent_counter = 0

		# Color Correction

		# these will be added if it becomes verbose

		self.detector = None
		self.verbose = None
		self.updateParams(None)

		#Publisher
		self.pub_result = rospy.Publisher("~bot_existence", Bool, queue_size=1)

		#Subscriber
		self.sub_image = rospy.Subscriber("~image", CompressedImage, self.cbImage, queue_size=1)
		self.subswitch = rospy.Subscriber("~switch", BoolStamped, self.cbSwitch, queue_size=1)

		rospy.loginfo("[%s] Initialized (verbose = %s)" %(self.node_name, self.verbose))

		rospy.Timer(rospy.Duration.from_sec(2.0), self.updateParams)

	def updateParams(self):
		old_verbose = self.verbose
		self.verbose = rospy.get_param('~verbose', True)

		if self.verbose != old_verbose:
			self.loginfo('Verbose is now %r' % self.verbose)

		self.image_size = rospy.get_param('~img_size')
		self.top_cutoff = rospy.get_param('~top_cutoff')

	def cbSwitch(self, switch_msg):
		self.active = switch_msg.data

	def cbImage(self, image_msg):
		self.stats.received()

		if not self.active:
			return
		# Start Daemon thread to process the image
		thread = threading.Thread(target=self.processImage, args=(image_msg,))
		thread.setDaemon(True)
		thread.start()
		# Returns rightaway

	def loginfo(self, s):
		rospy.loginfo('[%s] %s' % (self.node_name, s))

	def intermittent_log_now(self):
		return self.intermittent_counter % self.intermittent_intervel == 1

	def intermittent_log(self):
		if not intermittent_log_now:
			return
		self.loginfo('%3d:%s' % (self.intermittent_counter, s))

	def processImage(self, image_msg):
		if not self.thread_lock.acquire(False):
			self.stats.skipped()
			#Return if the thread is locked
			return

		try:
			self.processImage_(image_msg)
		finally:
			self.thread_lock.release()

	def processImage_(self, image_msg):
		
		self.stats.processed()

		if self.intermittent_log_now():
			self.intermittent_log(self.stats.info())
			self.stats.reset()

		self.intermittent_counter += 1

		# Decode from compressed image with OpenCV
		try:
			image_cv = image_cv_from_jpg(image_msg.data)
		except ValueError as e:
			self.loginfo('Could not load image: %s' % e)
			return

		frame_id = image_msg.header.frame_id
		if frame_id <= BG_SAMPLE:
			#Compute background with the first 1000 images
			if frame_id == 1:
				self.background = image_cv
				self.bg_b, self.bg_g, self.bg_r = cv2.split(self.background)
			else:
				self.bg_b, self.bg_g, self.bg_r = self.getMidBackground(self.bg_b, self.bg_g, self.bg_r, image_cv)

			return

		elif frame_id == (BG_SAMPLE+1)
			self.background = cv2.merge(self.bg_b[:, :, BG_SAMPLE/2], self.bg_g[:, :, BG_SAMPLE/2], self.bg_r[:, :, BG_SAMPLE/2])

		self.bg_sum = sum(self.background)
		self.img_sum = sum(image_cv)

		self.loginfo('Background sum: %d' % (self.bg_sum))
		self.loginfo('Image sum: %d' % (self.img_sum))

		if (self.bg_sum - BG_WIDTH/2) <= self.img_sum <= (self.bg_sum + BG_WIDTH/2):
			self.pub_result.Publish(True)
		else:
			self.pub_result.Publish(False)

	def getMidBackground(self, bg_b, bg_g, bg_r, img):
		
		b, g, r = cv2.split(img)

		def sortList(li, el):
			for i in range(len(li)):
				for j in range(len(li[i])):
					for k in range(len(li[i][j])):
						if el[i][j] <= li[i][j][k]:
							li[i][j].insert(k, el[i][j])
							break
						elif k == (len(li[i][j])-1):
							li[i][j].append(el[i][j])
							break
			return li

		bg_b = sortList(bg_b, b)
		bg_g = sortList(bg_g, g)
		bg_r = sortList(bg_r, r)

		return bg_b, bg_g, bg_r

	def on_Shutdown(self):
		self.loginfo("Shutdown.")

class Stats(object):
	"""docstring for Stats"""
	def __init__(self):
		self.nresets = 0
		self.reset()

	def reset(self):
		self.nresets += 1
		self.t0 = time.time()
		self.nreceived = 0
		self.nskipped = 0
		self.nprocessed = 0
	
	def received(self):
		if self.nreceived==0 and self.nresets==1:
			rospy.loginfo('bot_detector_node received first image')

	def skipped(self):
		self.nskipped += 1

	def processed(self):
		if nreceived==0 and self.nresets==1:
			rospy.loginfo('bot_detector_node processing first image')

		self.nprocessed += 1

	def info(self):
		delta = time.time() - self.t0

		if self.nreceived:
			skipped_perc = (100 * self.nskipped / self.nreceived)
		else:
			skipped_perc = 0

		def fps(x):
			return '.1f fps' % (x / delta)

		m = 'In the last %.1f s: received %d (%s) processed %d (%s) skipped %d (%s) (%1.f%%)' % (delta, self.nreceived, fps(self.nreceived), self.nprocessed, fps(self.processed), self.nskipped, fps(self.nskipped), skipped_perc)
		return m 
		


if __name__ == '__main__':
	rospy.init_node('bot_detector', anonymous=False)
	bot_detector_node=BotDetectorNode()
	rospy.on_shutdown(bot_detector_node.on_Shutdown)
	rospy.spin()



