# ENPM692_Final
Final project for ENPM692 Manufacturing and Automation.

## Objective
The objective of this project was to create a MES system for tracking inventory, build requests, and process information for a manufacturing plant that makes agricultural backpack sprayers. 
This system provides the following benefits:
- Robust tracking of inventory amounts, status, batch traceability
- Easy-to-use build request system that checks required component amounts against available inventory 
- Real-time updates on status of build orders
- Complete traceability of the people, equipment, component batches, and per-unit process data for each build order

## Core Design Principles
1. This system is designed with the idea that process and inventory equipment would be connected to the MES system to perform tasks and data logging. This equipment includes label printers, digital scales, automated trolleys programmed with locations of all relevant stations, and semi-automated process equipment such as blow molders, injection molders, and test stations.
2. All materials (raw plastic, outsourced components, subassemblies/components manufactured in-house, and scrap) are tracked in the inventory tracker by container ID. These container IDs are printed on labels and applied to the containers themselves. 
3. All containers are delivered around the plant with autonomous trolleys. Containers may be loaded directly onto the trolley, may be placed in a bin that is carried by the trolley, or may be the bin itself. 
4. All production runs begin by requesting a build of a specified part or assembly. The request is rejected if there is not enough available inventory.
5. All production and inventory workers sign into MES stations that log detailed, timestamped information with every action they take, and prevent discrepancies with entered information. 

## Data Files
### Inventory Tracker
The inventory tracker is a csv file where each line represents a unique container and stores the following information about the contained components/subassemblies: 
- Drawing Number
- Description
- Vendor ("Internal" if manufactured in-house)
- Batch (Vendor batch number for outsourced, build order number for in-house)
- Quantity (# of components, or weight of raw plastic)
- Status (available, in use by [station ID], emptied)
### Build Orders
The build orders are .yaml files stored in the build_info folder. These files store all of the up-to-date information about a requested build, including:
- Name
- Name of desired component/assembly
- Drawing number of desired component/assembly
- Quantity of desired component/assembly
- Desired start date
- Estimated end date
- Current build status
- All required processes
- Current status of each process
- Component names, numbers, and quantities at each process

### Drawings
The "drawings" are .yaml files stored in the BOMS folder. They are named drawings because they would ideally be associated with an engineering drawing of the component or assembly being described. These files store all of the per-unit information about the component/assembly, including:
- Name
- Per Unit Weight
- Weight of container typically used to store item (could be a barrel, cardboard box, or bin)
- Processes required to make item
For each process, the following information is included:
- Process name
- Production rate (parts per hour)
- Name, drawing number, quantity, and quantity units for each component needed at that process

### Equipment Outputs
Production equipment and inventory scales would log data continuously to csv files within the equipment folder. These files are named after the equipment ID, which is on a bar code label on the equipment. Scanning the bar code allows the MES system to access the latest readings from this equipment. This logged data can also be useful for troubleshooting issues later on. 

### Station Logs
Station logs are csv files stored in the logs folder. These files are named according to station ID and station number. Logs are kept both for production MES screens and inventory MES screens. The files store a new timestamped line with each action that occurs when operating the MES system. This provides traceability for who was working at a certain process, what build they were working on, what container of material they were working with, or who checked a container in or out of inventory, and so on.

### Component Requests
The component requests file is a csv file that allows the inventory stations to see components requested by the process stations. These requests just contain the component drawing number, description, station requesting it, and request status. They are initially set to not complete, and then marked complete once the inventory manager checks out a container of that material.

## MES Interfaces
### Build Request MES Screen
The build request screen is used by a production manager to request a build. The production manager inputs their name, the drawing number of the desired product or component, name of the build, quantity needed, and desired start date. The system reads from the associated drawing, determines quantity of each component is required, and reads the inventory tracker to confirm there are enough available. If so, it generates a new build order file with all of the relevant information.

### Inventory MES Screen
The inventory MES screen allows an inventory manager (IM) to sign in and take the following actions:
- Add New Container - The IM prints a new container ID and applies it the container. They then scan the container ID, all other information, and weigh the container, and then add the new container to the inventory tracker.
- Check Out Container - The IM recieves component requests through the MES system. He selects a request, scans a container of the appropriate material, and checks it out so it can be delivered to the required station. If the scanned container ID does not match the requested material, it is rejected. When the material is checked out, its status in the inventory tracker is updated to in use - [station ID / number].
- Check In Container - After a container is checked out, it may be partially used and then checked back in. The IM recieves the partially used container, scans the ID, weighs it to get an updated quantity, and checks it back in. This updates the status of the container in the inventory tracker to available. 

### Production MES Screen
The production MES screen allows an operator to sign in to a station, request components, build parts, and send scrap or completed parts to inventory for storage. The operator must scan a build order, container IDs of their components, and equipment ID, which allows the MES system to:
- Confirm station is required for build
- Retrieve list of components for that station
- Confirm recieved containers contain the required components
- Print information labels for scrap/finished parts containers that are sent to inventory
- Update the build order file with build progress in real time
- Access equipment output data
