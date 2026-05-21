RAG_KNOWLEDGE = {
    "bow": {
        "Bath/Spa": {
            "aliases": ["bath", "bathtub", "spa", "hot tub", "soak"],
            "notes": ["Use when the text is about bathing/soaking/spa use."],
        },
        "River/Creek": {
            "definition" : """
              A creek is a water body that may be fed by rivers and other creeks. A creek is generally smaller in size than a river and is often characterised by intermittent
             water flow. Creeks can be prone to more extreme conditions of stasis in drought and flash flooding after rainfall.
             A river is a natural waterway that may be fed from other rivers of bodies of water draining water away 
             from a “catchment area”, to another location downstream. Rivers can vary in water flow, length, width and depth""",

            "aliases": ["river", "creek", "stream", "brook", "waterway", "channel","gully"],
            "notes": ["Use this for both river or creek."],
        },
        "Rocks": {
             "definition" : """
            Rock formations, cliff faces or rocky outcrops generally alongside the ocean.  """,
            "aliases": ["rocks", "cliff", "rock fishing"],
            "notes": ["Usually a fall from the rocks"],
        },
        "Beach": {
            "definition" : """
            The pebbly or sandy shore of a sea which is washed by the tide or waves. Also includes ocean baths, sea baths, tidal pools, and netted swimming enclosures that are located at and accessed from the shore (e.g. Ramsgate Baths, Wylie's Baths, Merewether Ocean Baths). These shore-accessed facilities are Beach, not Ocean/Harbour, even though they contain seawater.   """,
            "aliases": ["beach", "sand", "beachfront", "sandyshore", "baths", "ocean baths", "sea baths", "tidal pool", "swimming enclosure", "netted enclosure", "ocean pool"],
            "notes": ["Entering from a beach or shore-based facility, not deep out in the ocean. May refer to the name of an Australian beach. Ocean baths and netted sea enclosures accessed from shore = Beach, not Ocean/Harbour."],
        },
        "Swimming Pool": {
             "definition" : """
            A public swimming pool is a public, man-made structure capable of being filled with water and intended to be used for swimming,
              diving, wading or paddling, that cannot be emptied by a simple overturning of the structure. 
              This does not include individual therapeutic tubs or baths used for cleansing of the body 8. 
              This category includes pools known to be open to the public including rock pools, municipal.
                 Constructed aquatic amusements in a public space (i.e. no access restrictions) such as water slides or zero depth splash playgrounds.
                A swimming pool that is situated, proposed to be constructed or installed on premises on which a residential building is located 6. Includes both indoor and outdoor pools at residential locations.
                Swimming pool at a motel, hotel, resort, caravan park etc. A pool at a place of non-permanent residence.
                Any moveable structure intended for swimming or other water recreation. Examples include wading pools, inflatable pools and “soft-sided, self-rising” pools 7.
                Artificially constructed body of water intended for the purpose of recreation located in a public space i.e. no access restrictions. E.g. South Bank Beach in Brisbane. 

   """,
            "aliases": ["pool", "rock pool"],
            "notes": ["can be any type of swimming pool"],
        },




        "Lake/Dam": {
             "definition" : """
            A lake is a body of water either fresh or salt water which is of considerable size and surrounded by land.
            May be an enclosed body of water with banks or barriers on all sides. They may also have one wall and use gravity
              of water flow to ensure the water remains contained. 
              Dams may vary in size and depth, with recreational dams capable of being large and farm dams generally 
              being smaller in size. Often they are not fenced due to being used for the needs of animals on farms.


   """,
            "aliases": ["lake", "dam"],
            "notes": ["use if either lake or dam or related"],
        },

        "Ocean/Harbour": {
             "definition" : """
            An open expanse of water that is generally accessed via a jetty or watercraft i.e. not the sandy shore of a beach entry.
            Vast body of open water – may be unprotected – includes sea and drowning deaths that occur offshore. Must be within Australian territorial waters to be included in database.
            Harbour is more protected than ocean, also includes river mouth areas including bays.
            IMPORTANT: Ocean baths, sea baths, tidal pools, and netted swimming enclosures accessed from shore are NOT Ocean/Harbour — they are Beach. Only use Ocean/Harbour when the person was in open, unenclosed ocean or harbour water.   """,
            "aliases": ["offshore", "open ocean", "open water", "harbour", "harbor", "bay", "inlet"],
            "notes": ["Distinct from Beach: Beach is the sandy shore entry or a shore-based enclosed facility (baths, ocean pool). Ocean/Harbour is open water away from shore, accessed by boat or jetty."],
        },




             "Other": {
             "definition" : """
            If a body of water is mentioned, but does not fit into any of the other categories

   """,
            "aliases": ["toilet", "tank"],
            "notes": ["use if body of water does not fit into any definitions above"],
        },
    },

"activity": {
        "Bathing": {
            "definition" : """
            Submerging the body in water for the purposes of relaxation or cleaning. Generally not vigorous activity.
            """,
            "aliases": ["bath", "bathed"],
            "notes": ["When these terms appear, choose Option A."],
        },
        "Boating": {
        "definition" : """
            Watercraft that features an engine or power external to waves and human momentum.
            Watercraft that does not have an engine or external power source. Generally powered by waves and human exertion. 
            """,
            "aliases": ["vessel", "boat","Jet boat", "Water Skiing","Motorised Boat","Fishing boat","Kayaking","Canoeing"],
            "notes": ["use if any type of aquatic vessel that is boat related"],
        },
        "Diving": {
            "definition" : """
            The sport or activity of exploring or swimming under water. This category includes activities related to diving
              where the person was already in and or submerged by water prior to drowning eg spear fishing 
            """,
            "aliases": ["Cave Diving","Free Diving", "Scuba Diving","Skin Diving","Snorkelling","Spear Fishing"
            ],
            "notes": ["anything relating to underwater activity"],
        },
         "Fall": {
            "definition" : """
                This is when a person was not intending to be in water and fell in usually standing near the water.Unintentional entry into the water from land.
            """,
            "aliases": ["Fall whilst walking near water","Fall whilst playing near water" ,"Fall whilst cleaning the pool" ],
        },
           "Fishing": {
            "definition" : """
                The act of catching fish from all environments except those classified as rock fishing. Fishing from rocks, rocky outcrops and cliffs must be coded as ‘Rock Fishing’.
            """,
            "aliases": ["fishing from beach","fishing from bridge","fishing from jetty/pier","fishing from sitll water edge","fishing whilst in the water" ],
            "notes": ["anything relating to underwater activity"],
        },
               "Jumped In": {
            "definition" : """
                The act of intentionally jumping in the water from a variety of different objects.             """,
            "aliases": ["dive entry","from bridge","from tree","from water's edge","from rocks" ],
            "notes": ["different from fall as it was intentional"],
        },
                 "Non-aquatic Transport": {
            "definition" : """
                Operating any kind of vehicle, otherwise not classified under watercraft (powered and unpowered).       """,
            "aliases": ["Bicycle","fcar","helicoptor","motobike","paraglider", "plane","quad bike","machinery","ride on mower","truck"],
            "notes": ["usually not intentially entering into the water"],
        },
               "Other": {
            "definition" : """
               Not able to be coded into any of the above categories     """,
           
        },
            "Rescue": {
            "definition" : """
               The act of attempting to pull an object, animal or person out of the water who may be in danger.     """,
            "aliases": ["of a human","of an animal","of an object"],
            "notes": ["this is relating to the person that drowned only not if they were rescued by someone else"],
        },
        "Rock Fishing": {
            "definition" : """
               Fishing from rocks, rocky outcrops, cliffs. This activity should always be linked to the location grouping of rocks.    """,
            "aliases": ["Fall into water while rock fishing"],
        },
         "Swept Away": {
            "definition" : """
               This is relating to a flood only if they were swept away by floodwaters  """,
            "aliases": ["swept away by flood"],
        },
           "Swept In": {
            "definition" : """
                    pulled into water while recreating or standing near the waters edge
             """,
            "aliases": ["Eg child swept in whilst father rock fishing from rocks","Swept in whilst playing near water","Swept in whilst walking near water"],
        },
        "Swimming and Recreating": {
            "definition": """
                The person was intentionally swimming, wading, playing in the water, or engaging in recreational water activity
                at the time of the incident. This is the most common activity for drowning fatalities.
                Use this when the person was voluntarily in the water for leisure or exercise.
            """,
            "aliases": ["swimming","swim","wading","playing in water","recreating in water","water play","snorkelling at surface","paddling","floating","swimmer"],
            "notes": [
                "Use this for general recreational swimming — not diving (use Diving) or watercraft (use Watercraft).",
                "Distinguish from Swept In: Swimming and Recreating means the person chose to enter the water; Swept In means they were pulled in unintentionally. This value can be assumed if the person was in a swimming pool etc.",
            ],
        },
              "Unknown": {
            "definition" : """
                   It is not known what activity was being conducted immediately prior to drowning. If the text is unlcear on how the person entered the water and makes no indication.  May often be as a result of person undertaking activity alone and therefore there may be not witnesses to the activity prior to drowning
             """,
        },
         "Unlikely to be Known": {
            "definition" : """
                This is when case is re-evaulated and the date is old and we will likely never know the activity
             """,
        },
            "Watercraft": {
            "definition" : """
                This is a water related vessel that is not a boat, can be towed behind a boat like skiing, tubing, waterboarding. It be surfing,
                boogie boarding. Can be hopping on watercraft from jetty to land or pontoon and ladning on watercrapft. It also
                included jumping off of watercraft
             """,
         "aliases": ["surfing","boogie boarding","water skiing","jet skiing","dingy onto yacht"],

        },
         },

    "sex": {
        "Male": {
    
            "aliases": ["man", "son","he","old man","boy"],
            "notes": ["When the person that drowned is male choose this"],
        },
      "Female": {
    
            "aliases": ["girl", "daughter","she","old woman","woman"],
            "notes": ["When the person that drowned is female choose this"],
        },
        "Unkown": {

            "notes": ["when the sex of the deceased is Unknown or not mentioned"],
        }
         },



    "rules": [
        "Choose exactly one activity from ACTIVITY_CHOICES.",
        "Choose exactly one bow from BOW_CHOICES.",
        "Choose exactly one sex from SEX_CHOICES"
        "If multiple matches occur, choose the most central / explicit one.",
        "If nothing matches clearly, choose the closest only if justified by the text.",
    ],
}