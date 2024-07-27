/*
    Use this mechanism for changes that must be refreshed every time the data within the page changes.
    Notably, the schedule view updates periodically (once a minute) as well as when the use interacts by navigating 
    to a separate day.  Thus a UI change that needs to correlate with the currently displayed schedule can use this
    mechanism to insert updates every time the schedule does.
*/
function background_svg(left_edge, right_edge) {
    /* unescaped svg for background image:
        <svg width="100" height="100" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect x="0" y="0" w="100" h="100" stroke-width="0" fill="rgba(0,0,139,0.15)"/>
        </svg>
    */
    return "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect x='" + 
        left_edge + "' y='0' width='" + right_edge + 
        "' height='100' fill='rgba(0,0,139,.15)'/%3E%3C/svg%3E\")";
}

function diurnal_display_update_schedule() {
    if ($('#displayScheduleDate').length > 0) {
        $.get( "/diurnal_display-data", {"date" : toXSDate(displayScheduleDate)}, function( diurnal_data ) {
            $(".stationSchedule .scheduleTick").each( function() {
                var cellTime = parseInt($(this).attr("data")) * 60;
                if (cellTime < diurnal_data.sunrise + 60) {
                    var x = 0;
                    var w = Math.max(0,Math.min(100,(diurnal_data.sunrise - cellTime)/60*100));
                    $(this).css({
                        "background-image" : background_svg(x, w),
                        "background-size" : "cover"
                    });
                } else if (cellTime > diurnal_data.sunset - 60) {
                    var x = Math.max(0,Math.min(100,(diurnal_data.sunset - cellTime)/60*100));
                    var w = 100;
                    $(this).css({
                        "background-image" : background_svg(x, w),
                        "background-size" : "cover"});
                } else {
                    $(this).css({"background-image" : ""});
                }
            });
        });
    }
}

jQuery(document).ready(function(){
    // An observer will monitor an element of the UI and trigger every time it changes.
    // In this case, every time the schedule view for the home page is updated we know that "displayScheduleDate" changes, 
    // and we can piggyback on that to make our own UI changes
    
    if (window.location.pathname == "/") {
        if ($('#displayScheduleDate').length > 0) {
            // Verify the schedule is available (i.e. not in Manual mode)
            observer = new MutationObserver(diurnal_display_update_schedule);
            observer.observe($('#displayScheduleDate')[0], {characterData: true, childList:true, subTree: true});
        }
    }
});

