PAPER_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A2": (420.0, 594.0),
    "A1": (594.0, 841.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
}

DICTIONARIES = {
    **{
        f"DICT_{bits}X{bits}_{count}": count
        for bits in range(4, 8)
        for count in (50, 100, 250, 1000)
    },
    "DICT_ARUCO_ORIGINAL": 1024,
    "DICT_APRILTAG_16h5": 30,
    "DICT_APRILTAG_25h9": 35,
    "DICT_APRILTAG_36h10": 2320,
    "DICT_APRILTAG_36h11": 587,
    "DICT_ARUCO_MIP_36h12": 250,
}

CHARUCO_DICTIONARIES = {k: v for k, v in DICTIONARIES.items() if k.startswith("DICT_") and "X" in k}
# Keep all printable content outside the unprintable edge area of common printers.
EDGE_CLEARANCE_MM = 4.5
