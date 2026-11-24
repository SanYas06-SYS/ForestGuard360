"""Small local patrol polygons in [latitude, longitude] order."""
import math

def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def on_segment(a,b,p):
    return abs(cross(a,b,p))<1e-10 and all(min(a[i],b[i])-1e-10<=p[i]<=max(a[i],b[i])+1e-10 for i in (0,1))

def intersects(a,b,c,d):
    return (cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0) or any((on_segment(a,b,c),on_segment(a,b,d),on_segment(c,d,a),on_segment(c,d,b)))

def validate_area(value):
    if not isinstance(value,list) or not 3<=len(value)<=100:raise ValueError('Draw a border with 3 to 100 points.')
    points=[]
    for point in value:
        if not isinstance(point,list) or len(point)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in point):raise ValueError('Invalid area point.')
        if not -90<=point[0]<=90 or not -180<=point[1]<=180:raise ValueError('Area points must be on the map.')
        points.append([float(point[0]),float(point[1])])
    if points[0]==points[-1]:points.pop()
    if len(points)<3 or len({tuple(p) for p in points})!=len(points):raise ValueError('Use at least three distinct border points.')
    if max(p[1] for p in points)-min(p[1] for p in points)>180:raise ValueError('Draw a local area that does not cross the date line.')
    n=len(points)
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1):continue
            if intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):raise ValueError('Border lines must not cross or touch each other.')
    area=sum(points[i][0]*points[(i+1)%n][1]-points[(i+1)%n][0]*points[i][1] for i in range(n))
    if abs(area)<1e-10:raise ValueError('Draw an area, not a straight line.')
    return points

def contains(area,latitude,longitude):
    if not area:return False
    p=(float(latitude),float(longitude));inside=False
    for i,a in enumerate(area):
        b=area[(i+1)%len(area)]
        if on_segment(a,b,p):return True
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside
