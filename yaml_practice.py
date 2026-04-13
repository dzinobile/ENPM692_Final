import yaml
import os

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
BUILD_INFO_DIR = os.path.join(BASE_DIR, "build_info")


def read_build_info(build_number: str) -> dict:
    """Read a build info YAML file by build number (e.g. '00003')."""
    filepath = os.path.join(BUILD_INFO_DIR, f"{build_number}.yaml")
    with open(filepath, "r") as f:
        return yaml.safe_load(f)


def write_build_info(build_number: str, data: dict) -> None:
    """Write a build info dict back to its YAML file."""
    filepath = os.path.join(BUILD_INFO_DIR, f"{build_number}.yaml")
    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    build_number = "00003"

    # --- READ ---
    print(f"Reading build {build_number}...")
    build = read_build_info(build_number)

    print(f"  Name:       {build['Name']}")
    print(f"  Quantity:   {build['Quantity']}")
    print(f"  Status:     {build['Status']}")
    print(f"  Start Date: {build['Start Date']}")
    print(f"  End Date:   {build['End Date']}")

    for process in build.get("Processes", []):
        print(f"\n  Process: {process['Name']}")
        print(f"    Status:          {process['Status']}")
        print(f"    Parts Completed: {process['Parts Completed']} / {process['Total Parts']}")
        for component in process.get("Components", []):
            print(f"    Component: {component['Name']}  "
                  f"(qty: {component['Quantity']} {component['Units']}, "
                  f"dwg: {component['Drawing Number']})")

    # --- WRITE (update a field and save) ---
    print(f"\nUpdating status of build {build_number} to 'In Progress'...")
    build["Status"] = "In Progress"
    build["Processes"][0]["Status"] = "In Progress"
    build["Processes"][0]["Parts Completed"] = 3

    write_build_info(build_number, build)
    print("Saved.")

    # --- READ BACK to confirm ---
    print("\nReading back to confirm changes...")
    updated = read_build_info(build_number)
    print(f"  Status:          {updated['Status']}")
    print(f"  Parts Completed: {updated['Processes'][0]['Parts Completed']}")
