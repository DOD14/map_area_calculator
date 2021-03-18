import argparse
import cv2
import numpy as np
import os
from pathlib import Path

# show image and wait for key before proceeding
def imshow_wait(title, image):
	
    # resize large images to a comfortable width
    max_width = 720
    width, height = image.shape[0], image.shape[1]
	
    if width > max_width:
        aspect_ratio = height/width
        new_height = max_width * aspect_ratio
        resized_image = cv2.resize(image.copy(), (int(new_height), max_width))
    else:
        resized_image = image		

    # show resized image
    cv2.imshow(title, resized_image)
    key = cv2.waitKey(0) & 0xFF
    cv2.destroyWindow(title)

# will be storing our results in this string in csv format
measurements = "College,Pale area,Dark area,Green area\n"

# empirical color bounds to get various contours and regions
low_orange = (130, 190, 230)
high_orange = (140, 200, 255)
low_pale_green = (223,233,223)
high_pale_green = (227,237,227)
low_dark_green = (190,215,180)
high_dark_green = (195,220,190)

# parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-d", "--dataset", help="path to folder containing images to be processed")
ap.add_argument("-r", "--results", help="file in which results will be recorded")
ap.add_argument("-v", "--verbose", default=False, action='store_true', help="use flag to display images for each processing step")
ap.add_argument("-s", "--save", nargs='?', help="optional: path to folder where resultant images will be stored")
args = vars(ap.parse_args())
print('[i] parsed arguments: ' + str(args))
save_dir = args['save']

# get the images in the dataset folder
image_dir = Path(args['dataset'])
image_paths = sorted([path for path in image_dir.iterdir()])

# loop over image paths
for img_path in image_paths:
    
    # prevent an annoying bug that attempts to read hidden files
    filename = Path(img_path).name
    if filename.startswith("."):
        print('[i] skipping file: ' + filename)
        continue

    # load image
    print('[i] processing image: ' + filename)
    image = cv2.imread(str(img_path))

    # get orange regions (on our map they enclose Colleges)
    orange_mask = cv2.inRange(image, low_orange, high_orange)

    # connect patchy contours 
    orange_mask = cv2.GaussianBlur(orange_mask, (9, 9), 0) # blur
    edges = cv2.Canny(orange_mask, 25, 200) # detect edges
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=10, maxLineGap=50) # detect lines despite gaps
    for line in lines: # loop over lines and draw them over the disconnected edges
        x1, y1, x2, y2 = line[0]
        cv2.line(edges, (x1, y1), (x2, y2), 255, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(50,50))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel) # patch it up a bit more

    # get all continuous contours, draw only the largest one (must be enclosing entire College) and fill it in
    # in other words get a mask that covers College grounds
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key = cv2.contourArea, reverse = True)
    black_canvas = np.zeros_like(image)
    college_grounds_mask = cv2.drawContours(black_canvas, contours, 0, (255, 255, 255), -1)
    college_grounds_mask = cv2.cvtColor(college_grounds_mask, cv2.COLOR_BGR2GRAY)

    # get all green spaces (on our map they come in two shades of green)
    pale_green_mask = cv2.inRange(image, low_pale_green, high_pale_green)
    dark_green_mask = cv2.inRange(image, low_dark_green, high_dark_green)

    # combine the two kinds of green spacesi into one
    combined_green_mask = cv2.bitwise_or(pale_green_mask, dark_green_mask)

    # get only the green spaces on College grounds
    green_college_grounds = cv2.bitwise_and(college_grounds_mask, combined_green_mask)
    pale_green_college_grounds = cv2.bitwise_and(college_grounds_mask, pale_green_mask)
    dark_green_college_grounds = cv2.bitwise_and(college_grounds_mask, dark_green_mask)

    # get the pixels per metre in our image
    # this information makes up part of the filename
    # and was noted when exporting the online map
    college, metres, pixels = filename.split(".")[0].split("_")
    metres = int(metres.strip("m"))
    pixels = int(pixels.strip("px"))
    pxpm = pixels/metres 

    # count the bright pixels in our final image and convert to metres squared
    nonzero = cv2.countNonZero(green_college_grounds)
    green_area = str(int(round(nonzero/(pxpm * pxpm))))
    
    nonzero_pale = cv2.countNonZero(pale_green_college_grounds)
    pale_area = str(int(round(nonzero_pale/(pxpm * pxpm))))
    
    nonzero_dark = cv2.countNonZero(dark_green_college_grounds)
    dark_area = str(int(round(nonzero_dark/(pxpm * pxpm))))

    # add our measurement to the measurements.txt file
    print('\t[i] College: ' + college + "\n\t[i] metres: " + str(metres) + "\n\t[i] pixels: " + str(pixels) + "\n\t[i] green area: " + green_area + " m^2")
    measurements += college + "," + pale_area + "," + dark_area + "," + green_area + "\n"
    
    if args['verbose'] == True or save_dir != None:
        # convert masks to BGR so that we can...
        orange_mask = cv2.cvtColor(orange_mask, cv2.COLOR_GRAY2BGR)
        closed = cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)
        college_grounds_mask = cv2.cvtColor(college_grounds_mask, cv2.COLOR_GRAY2BGR)
        pale_green_mask = cv2.cvtColor(pale_green_mask, cv2.COLOR_GRAY2BGR)
        dark_green_mask = cv2.cvtColor(dark_green_mask, cv2.COLOR_GRAY2BGR)
        combined_green_mask = cv2.cvtColor(combined_green_mask, cv2.COLOR_GRAY2BGR)
        green_college_grounds = cv2.cvtColor(green_college_grounds, cv2.COLOR_GRAY2BGR)
        
        # ...combine them into a single image...
        contours_row = cv2.hconcat([orange_mask, closed, college_grounds_mask, image])
        green_row = cv2.hconcat([pale_green_mask, dark_green_mask, combined_green_mask, green_college_grounds])
        all_images = cv2.vconcat([contours_row, green_row])
        
        # ...and show them on-screen...
        if args['verbose'] == True:
            imshow_wait(filename, all_images)
        
        # ...or save them to a directory
        if save_dir != None:
            save_dir = Path(save_dir)
            if not save_dir.is_dir():
                save_dir.mkdir()
            out_file = str(save_dir) + "/" + filename 
            cv2.imwrite(out_file, all_images)
            print("\t[i] wrote combined image to " + str(out_file))

# write out our measurements - done
with open(args['results'], 'w') as file:
	file.write(measurements)
