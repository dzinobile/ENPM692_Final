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

## System Components
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

### Build Request MES Screen
The build request screen is used by a production manager to request a build. The production manager inputs their name, the drawing number of the desired product or component, name of the build, quantity needed, and desired start date. The system 