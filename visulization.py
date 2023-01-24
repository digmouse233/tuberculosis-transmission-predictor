import os
import shutil

import xlsxwriter
from pdf_annotate import Appearance
from pdf_annotate import PdfAnnotator
from pdf_annotate import Location

import colors
import io_operations
import k_means
from cluster import get_clusters_kmeans
from cluster import find_adjacency
from border import graham_scan
from scale import get_scale_points
from scale import get_centroid
from intersects import is_intersects

READ_PATH = "geo_coordinates"
WRITE_PATH = "output"
PDF_PATH = "output"


def coloring(cluster, annotator, color, size):
    for building in cluster.buildings_lst:
        x = building.x
        y = building.y
        id = building.id
        x1 = x - size
        x2 = x + size
        y1 = 3370 - y - size
        y2 = 3370 - y + size
        annotator.add_annotation(
            annotation_type="square",
            location=Location(x1=x1, y1=y1, x2=x2, y2=y2, page=0),
            appearance=Appearance(fill=color, stroke_width=0),
        )
        annotator.add_annotation(
            annotation_type="text",
            location=Location(x1=x1, y1=y1, x2=x2, y2=y2, page=0),
            appearance=Appearance(content=id, fill=(1, 1, 1), font_size=5),
        )  # black text


def dfs_coloring(currently_coloring, adjacencies_number):
    if currently_coloring >= len(clusters_lst):
        return
    for color in range(adjacencies_number + 1):
        if can_use(color, currently_coloring):
            picked_color[currently_coloring] = color
            break
    dfs_coloring(currently_coloring + 1, adjacencies_number)


def can_use(color, currently_coloring):
    for colored in range(currently_coloring):
        if (
            adjacencies[colored][currently_coloring] == 1
            or adjacencies[currently_coloring][colored] == 1
        ):
            if picked_color[colored] == color:
                return False
    return True


def draw_border(cluster, annotator, color):
    buildings = []
    for building in cluster.buildings_lst:
        buildings.append((building.x, 3370 - building.y))
    hull = graham_scan(buildings)
    print(f"Hull: {hull}")

    annotator.add_annotation(
        annotation_type="polyline",
        location=Location(points=hull, page=0),
        appearance=Appearance(fill=color, stroke_width=5),
    )

    return hull


def draw_scaled_border(cluster, annotator, color, scale_number):
    buildings = []
    for building in cluster.buildings_lst:
        buildings.append((building.x, 3370 - building.y))
    hull = graham_scan(buildings)
    scaled_hull = get_scale_points(hull, scale_number)
    centroid = get_centroid(buildings)
    print(f"Scaled_hull: {scaled_hull}")
    print(f'Centriod: {centroid}')

    annotator.add_annotation(
        annotation_type="polyline",
        location=Location(points=scaled_hull, page=0),
        appearance=Appearance(fill=color, stroke_width=5),
    )

    annotator.add_annotation(
        annotation_type="circle",
        location=Location(points=centroid, page=0),
        appearance=Appearance(fill=color)
    )

    return scaled_hull


if __name__ == "__main__":
    files = io_operations.get_files(PDF_PATH)
    print(f"Total File: {len(files)}")
    print(f"Files List: {files}")
    for file in files:
        # to check if file is a .pdf file
        if ".pdf" not in file:
            continue

        print(f"\nCurrent File: {file}")
        map_name = file.split("_Building")[0]
        map = map_name + ".xls"

        cluster_number = k_means.get_cluster_number(READ_PATH, map)
        print(cluster_number)

        # Create different directories to store the data of different granularity
        for k_value in cluster_number:
            print(PDF_PATH + "/" + file)
            try:
                shutil.copy(
                    PDF_PATH + "/" + file, PDF_PATH + "/" + map_name + f"/k_{k_value}/"
                )
            except:
                os.makedirs(PDF_PATH + "/" + map_name + "/" + f"k_{k_value}/")
                print("create dir")
                shutil.copy(
                    PDF_PATH + "/" + file, PDF_PATH + "/" + map_name + f"/k_{k_value}/"
                )

            clusters_lst = get_clusters_kmeans(READ_PATH, map, k=k_value)
            adjacencies = find_adjacency(clusters_lst, k_value)

            print("Adjacency Matrix: ")
            for i in range(len(adjacencies)):
                print(adjacencies[i])

            picked_color = [-1 for _ in range(len(clusters_lst))]
            picked_color[0] = 1
            dfs_coloring(1, len(adjacencies))

            print("\nPicked Color:")
            print(picked_color)

            annotator = PdfAnnotator(f"{PDF_PATH}/{map_name}/k_{k_value}/{file}")
            scaled_hulls = {}
            literally_adjacencies = {}
            for i in range(len(picked_color)):
                current_cluster_id = clusters_lst[i].get_cluster_id()
                print(f"Current Cluster ID: {current_cluster_id}")
                literally_adjacencies[clusters_lst[i].get_cluster_id()] = []
                color = colors.COLORS[picked_color[i] % 7]
                r, g, b = color[0] / 255, color[1] / 255, color[2] / 255
                coloring(clusters_lst[i], annotator, (r, g, b, 1), size=10)

                hull = draw_border(clusters_lst[i], annotator, (r, g, b, 1))
                current_scaled_hull = draw_scaled_border(
                    clusters_lst[i], annotator, (r, g, b, 1), scale_number=1.5
                )

                if scaled_hulls:
                    for cluster_id, scaled_hull in scaled_hulls.items():
                        if is_intersects(current_scaled_hull, scaled_hull):
                            literally_adjacencies[cluster_id].append(
                                clusters_lst[i].get_cluster_id()
                            )
                            literally_adjacencies[
                                clusters_lst[i].get_cluster_id()
                            ].append(cluster_id)

                print("Literally Adjacency")
                print(literally_adjacencies)

                scaled_hulls[clusters_lst[i].get_cluster_id()] = current_scaled_hull

                print(
                    "Coloring cluster {} using color(r, g, b): {} {} {}".format(
                        str(i), str(r), str(g), str(b)
                    )
                )
                annotator.write(f"{WRITE_PATH}/{map_name}/k_{k_value}/{file}")

            print("Literally Adjacencies")
            print(literally_adjacencies)

            try:
                os.remove(f"{PDF_PATH}/{map_name}/k_{k_value}/clusters_data.xlsx")
            except:
                pass

            workbook = xlsxwriter.Workbook(
                f"{PDF_PATH}/{map_name}/k_{k_value}/clusters_data.xlsx"
            )
            io_operations.save_clusters_data(clusters_lst, workbook)
            io_operations.save_adjacencies_data(literally_adjacencies, workbook)
            workbook.close()
