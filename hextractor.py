import os
import sys
import pathlib
import argparse
import tarfile
import zipfile
import json
import platform


import pycdlib


def install_data_product(iso, files_json, dest):
    with iso.open_file_from_iso(rr_path=f"/data/{files_json}") as h:
        files = json.load(h)
    file_archives = set()
    for f, metadata in files.items():
        file_archives.add(metadata[0])
    # TODO write filelist
    for tar in file_archives:
        with iso.open_file_from_iso(rr_path=f"/data/{tar}") as tar_handle:
            with tarfile.open(mode="r", fileobj=tar_handle) as t:
                if hasattr(tarfile, "data_filter"):
                    t.extractall(path=dest, filter="tar")
                else:
                    t.extractall(path=dest)

def recursive_expansion(str_fmt, var_dict):
    while True:
        expanded = str_fmt.format(**var_dict)
        if expanded == str_fmt:
            break
        str_fmt = expanded
    return str_fmt

def main(args):

    iso_path = pathlib.Path(args.iso)

    iso = pycdlib.PyCdlib()
    iso.open(iso_path)

    # Data Products
    try:
        with iso.open_file_from_iso(rr_path="/data/overview.json") as h:
            overview = json.load(h)
    except pycdlib.pycdlibexception.PyCdlibInvalidInput:
        print("Invalid SideFX Iso, missing '/data/overview.json'")
        return

    arg_product_map = {
        "License Server": "license_server",
        "HQueue Server": "hqueue_server",
        "HQueue Client": "hqueue_client",
        "Engine Maya": "engine_maya",
        "Engine Unity": "engine_unity",
        "Engine Unreal": "engine_unreal",
        "Houdini": "houdini",
        "Hserver": "hserver",
    }

    product_vals = vars(args)
    for product in overview["products"]:
        product_name = product["name"]
        try:
            arg_name = arg_product_map[product_name]
            if not product_vals[arg_name]:
                continue
        except KeyError:
            continue

        product_vals["iso_version"] = product["version"]
        dest = product_vals[f"{arg_name}_dir"]
        dest = recursive_expansion(dest, product_vals)
        print(f"Installing {product_name}")
        install_data_product(iso, product["files"], dest)

    # Packages
    packages_map = {
        "SideFXLabs": "sidefxlabs",
    }

    package_vals = vars(args)
    with iso.open_file_from_iso(rr_path="/packages/packages.json") as h:
        packages = json.load(h)
    for package in packages["packages"]:
        for basename,arg_name in packages_map.items():
            if package["name"].startswith(basename) and package_vals[arg_name]:
                dest = package_vals[f"{arg_name}_dir"]
                zip_name = f"{package['display_name']}.zip"
                package_name = basename
                break
        else:
            continue
        dest = recursive_expansion(dest, package_vals)
        print(f"Installing {package_name}")
        with iso.open_file_from_iso(rr_path=f"/packages/{zip_name}") as zip_handle:
            with zipfile.ZipFile(zip_handle, mode="r") as z:
                z.extractall(dest)

    # SHFS
    if args.shfs:
        dest = recursive_expansion(args.shfs_dir, package_vals)
        with iso.open_file_from_iso(rr_path="/data/houdini_shfs_files.json") as h:
            shfs_files = json.load(h)["files"]
        for dirname, dirlist, files in iso.walk(rr_path="/data/shfs/"):
            from_shfs = dirname[len("/data/shfs/"):]
            dest_dir = f"{dest}/{from_shfs}"
            if not os.path.exists(dest_dir):
                # TODO copy iso dir's permissions
                os.makedirs(dest_dir, mode=0o755)
            for iso_file in files:
                shfs_path = f"{from_shfs}/{iso_file}"
                if args.optional_shfs == False and shfs_files[shfs_path]["required"] == False:
                    continue
                iso.get_file_from_iso(
                    f"{dest_dir}/{iso_file}",
                    rr_path=f"{dirname}/{iso_file}"
                )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    if platform.system() == "Windows":
        install_root = "C:/Program Files/Side Effects Software"
        houdini_dir = "{install_root}/Houdini {iso_version}"
        shfs_dir = "{install_root}/shfs"
        sidefxlabs_dir = "{install_root}/sidefx_packages"
    elif platform.system() == "Linux":
        install_root = "/opt"
        houdini_dir = "{install_root}/hfs{iso_version}"
        shfs_dir = "{install_root}/sidefx/shfs"
        sidefxlabs_dir = "{install_root}/sidefx/sidefx_packages"
    else:
        raise OSError("No...just no")
    engine_maya_dir = "{houdini_dir}/engine/maya"
    engine_unity_dir = "{houdini_dir}/engine/unity"
    engine_unreal_dir = "{houdini_dir}/engine/unreal"

    parser.add_argument("iso", type=str, help="Offline iso image", metavar="{path_to_iso}")
    #parser.add_argument(
    #    "--dry-run",
    #    dest="dryrun",
    #    help="Report what will be done",
    #    action="store_true",
    #    default=False,
    #)
    parser.add_argument(
        "--install-houdini",
        dest="houdini",
        help="Install Houdini and the HDK",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--install-engine-maya",
        dest="engine_maya",
        help="Install Houdini Engine Maya Plugin",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--install-engine-unity",
        dest="engine_unity",
        help="Install Houdini Engine Unity Plugin",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--install-engine-unreal",
        dest="engine_unreal",
        help="Install Houdini Engine Unreal Plugin",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--install-sidefxlabs",
        dest="sidefxlabs",
        help="Install SideFX Labs",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--install-shfs",
        dest="shfs",
        help="Install Shared Houdini File System (SHFS)",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--install-optional-shfs",
        dest="optional_shfs",
        help="Install Optional Shared Houdini File System (SHFS)",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--houdini-dir",
        dest="houdini_dir",
        help="Houdini install location",
        type=str,
        default=houdini_dir,
        metavar="{houdini_dir}",
    )
    parser.add_argument(
        "--engine-maya-dir",
        dest="engine_maya_dir",
        help="Houdini Engine Maya install location",
        type=str,
        default=engine_maya_dir,
        metavar="{engine_maya_dir}",
    )
    parser.add_argument(
        "--engine-unity-dir",
        dest="engine_unity_dir",
        help="Houdini Engine Unity install location",
        type=str,
        default=engine_unity_dir,
        metavar="{engine_unity_dir}",
    )
    parser.add_argument(
        "--engine-unreal-dir",
        dest="engine_unreal_dir",
        help="Houdini Engine Unreal install location",
        type=str,
        default=engine_unreal_dir,
        metavar="{engine_unreal_dir}",
    )
    parser.add_argument(
        "--sidefxlabs-dir",
        dest="sidefxlabs_dir",
        help="SideFX Labs install location",
        type=str,
        default=sidefxlabs_dir,
        metavar="{sidefxlabs_dir}",
    )
    parser.add_argument(
        "--shfs-dir",
        dest="shfs_dir",
        help="Shared Houdini File System (SHFS) install location",
        type=str,
        default=shfs_dir,
        metavar="{shfs_dir}",
    )
    parser.add_argument(
        "--install-root",
        dest="install_root",
        help="Optional Install Root Directory, {install_root} will be replaced with this path",
        type=str,
        default=install_root,
        metavar="{install_root}",
    )

    args = parser.parse_args()

    main(args)
